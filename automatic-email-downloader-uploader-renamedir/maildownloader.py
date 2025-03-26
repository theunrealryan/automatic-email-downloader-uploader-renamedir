import imaplib
import email
import os
import time
import logging
import re
import socket
import unicodedata  # Importado para normalização dos caracteres
from email.header import decode_header
from logging.handlers import RotatingFileHandler

# CONFIGURAÇÃO GLOBAL DO SOCKET  
# Aumenta o timeout para 120 segundos, reduzindo erros de conexão em e-mails grandes.
socket.setdefaulttimeout(120)

# CONFIGURAÇÃO DE SERVIDOR  
IMAP_SERVER = ""  # Endereço do servidor IMAP
IMAP_PORT = 143                # Porta padrão IMAP (143 para STARTTLS, 993 para SSL)
USE_SSL = False                # Se True, usará IMAP4_SSL, senão IMAP4 normal
IMAP_PASSWORD = ""

# Lista de contas de e-mail a serem arquivadas
EMAIL_ACCOUNTS = [
    ""  
]

# Diretório base para armazenar as pastas locais
MAILSTORE_HOME = ""

# Número de retentativas de FETCH em caso de falha de conexão
FETCH_RETRIES = 3
FETCH_DELAY = 5  # segundos de espera entre as tentativas

# Número máximo de reconexões ao servidor, caso o socket caia
MAX_RECONNECTS = 3

# FUNÇÃO PARA NORMALIZAR O EMAIL (REMOVENDO CARACTERES NÃO ASCII)  
def normalize_email(email_address: str) -> str:
    """
    Normaliza o endereço de e-mail, removendo caracteres não-ASCII.
    """
    return unicodedata.normalize('NFKD', email_address).encode('ascii', 'ignore').decode('ascii')

# INICIALIZAÇÃO DE LOG  
def init_logger():
    """
    Configura o logger global com StreamHandler e RotatingFileHandler,
    removendo handlers existentes para evitar duplicações.
    """
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)

    # Remove handlers antigos (caso o script seja chamado mais de uma vez)
    while logger.handlers:
        logger.removeHandler(logger.handlers[0])

    # Formato do log
    log_format = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")

    # Handler para console
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(log_format)

    # Handler para arquivo com rotação (2 MB, até 5 backups)
    file_handler = RotatingFileHandler(
        "email_archive.log",
        maxBytes=2 * 1024 * 1024,
        backupCount=5,
        encoding="utf-8"
    )
    file_handler.setFormatter(log_format)

    logger.addHandler(console_handler)
    logger.addHandler(file_handler)
    return logger

# FUNÇÕES AUXILIARES  
def get_local_username(email_address: str) -> str:
    """
    Extrai a parte local do endereço de e-mail (antes do '@').
    Exemplo: 'acaosocial' de 'acaosocial@congonhinhas.pr.gov.br'.
    """
    return email_address.split('@')[0]

def create_folder(path: str):
    """
    Cria um diretório local, sem erro se já existir.
    """
    try:
        os.makedirs(path, exist_ok=True)
    except Exception as e:
        logging.error(f"Não foi possível criar a pasta '{path}': {e}", exc_info=True)

def decode_subject(subject: str) -> str:
    """
    Decodifica o cabeçalho 'Subject' (RFC 2047), tratando Base64, Quoted-Printable etc.
    """
    decoded_fragments = decode_header(subject)
    decoded_subject = ""
    for fragment, encoding in decoded_fragments:
        if not encoding or encoding.lower() == "unknown-8bit":
            encoding = "utf-8"
        if isinstance(fragment, bytes):
            try:
                decoded_fragment = fragment.decode(encoding, errors="replace")
            except LookupError:
                decoded_fragment = fragment.decode("utf-8", errors="replace")
            decoded_subject += decoded_fragment
        else:
            decoded_subject += fragment
    return decoded_subject

def sanitize_filename(name: str, default: str = "sem_assunto", max_length: int = 50) -> str:
    """
    Remove caracteres indesejados do nome de arquivo e limita o tamanho.
    """
    if not name:
        name = default
    name = re.sub(r"[^a-zA-Z0-9\s]", "", name)
    name = "_".join(name.split())
    return name[:max_length]

def connect_imap_server(email_account: str, password: str, use_ssl: bool, host: str, port: int):
    """
    Conecta ao servidor IMAP, com ou sem SSL, e faz login na conta especificada.
    Retorna o objeto 'mail' (instância de IMAP4 ou IMAP4_SSL).
    """
    if use_ssl:
        mail_conn = imaplib.IMAP4_SSL(host, port)
    else:
        mail_conn = imaplib.IMAP4(host, port)

    mail_conn.login(email_account, password)
    return mail_conn

# FUNÇÃO DE FETCH COM RECONEXÃO  
def fetch_email_with_retry(mail_ref, email_id, mailbox_name,
                           fetch_retries, fetch_delay, reconnect_callback):
    """
    Executa FETCH para um email_id, com 'fetch_retries' tentativas.
    Se todas falharem por erro de socket, retorna (None, None).
    Em caso de falha, chama 'reconnect_callback()' para reconectar.
    'mail_ref' é um dicionário contendo 'mail': <objeto IMAP>.
    """
    for attempt in range(fetch_retries):
        try:
            status, data = mail_ref["mail"].fetch(email_id, "(RFC822)")
            return status, data
        except (imaplib.IMAP4.abort, socket.error) as e:
            logging.warning(
                f"Tentativa {attempt+1} de {fetch_retries} falhou para e-mail ID {email_id.decode('utf-8')}, "
                f"pasta '{mailbox_name}': {e}"
            )
            # Tenta reconectar
            reconnect_ok = reconnect_callback()
            if not reconnect_ok:
                # Se não conseguir reconectar, não adianta continuar
                break
            # Tenta novamente após um delay
            time.sleep(fetch_delay)
        except Exception as e:
            logging.warning(
                f"Erro inesperado na tentativa {attempt+1} de {fetch_retries} para e-mail ID {email_id.decode('utf-8')}: {e}"
            )
            time.sleep(fetch_delay)
    return None, None

# DOWNLOAD DA PASTA (COM RECONEXÃO COMPLETA SE PRECISO)  
def download_mailbox(mail_ref, user_base_dir: str, mailbox_name: str,
                     email_account: str, password: str,
                     use_ssl: bool, host: str, port: int,
                     max_reconnects: int):
    """
    Seleciona a pasta IMAP 'mailbox_name' e baixa todos os e-mails,
    criando um diretório local com o mesmo nome.
    'mail_ref' é um dicionário contendo 'mail': <IMAP connection>.
    """

    # Contador de reconexões
    reconnect_count = [0]

    def reconnect_callback():
        """
        Fecha a conexão atual e cria uma nova. 
        Se exceder max_reconnects, retorna False.
        """
        if reconnect_count[0] >= max_reconnects:
            logging.error("Número máximo de reconexões atingido. Abandonando.")
            return False

        reconnect_count[0] += 1
        logging.info(f"Tentando reconectar... (tentativa {reconnect_count[0]}/{max_reconnects})")
        try:
            mail_ref["mail"].logout()
        except Exception:
            pass

        try:
            new_mail = connect_imap_server(email_account, password, use_ssl, host, port)
            status, _ = new_mail.select(mailbox_name)
            if status != "OK":
                logging.error(f"Não foi possível selecionar a pasta '{mailbox_name}' após reconexão.")
                return False
            mail_ref["mail"] = new_mail  # Substitui a conexão
            return True
        except Exception as e:
            logging.error(f"Falha ao reconectar: {e}", exc_info=True)
            return False

    # Seleciona a pasta inicialmente
    status, _ = mail_ref["mail"].select(mailbox_name)
    if status != "OK":
        logging.error(f"Não foi possível selecionar a pasta '{mailbox_name}'.")
        return

    local_mailbox_path = os.path.join(user_base_dir, mailbox_name)
    create_folder(local_mailbox_path)

    # Busca todos os e-mails
    status, messages = mail_ref["mail"].search(None, "ALL")
    if status != "OK":
        logging.error(f"Erro ao buscar e-mails na pasta '{mailbox_name}'.")
        return

    email_ids = messages[0].split()
    logging.info(f"Baixando {len(email_ids)} e-mails de '{mailbox_name}' (conta: {email_account})...")

    for email_id in email_ids:
        status, data = fetch_email_with_retry(
            mail_ref=mail_ref,
            email_id=email_id,
            mailbox_name=mailbox_name,
            fetch_retries=FETCH_RETRIES,
            fetch_delay=FETCH_DELAY,
            reconnect_callback=reconnect_callback
        )
        if status != "OK" or data is None:
            logging.warning(
                f"Não foi possível buscar o e-mail ID {email_id.decode('utf-8')} na pasta '{mailbox_name}'."
            )
            continue

        raw_email = data[0][1]
        msg = email.message_from_bytes(raw_email)

        # Decodifica e sanitiza o assunto
        subject = msg.get("subject", "sem_assunto")
        subject = decode_subject(subject)
        sanitized_subject = sanitize_filename(subject)

        base_filename = f"{sanitized_subject}_{email_id.decode('utf-8')}.eml"
        local_filepath = os.path.join(local_mailbox_path, base_filename)

        # Evita sobrescrita
        counter = 1
        while os.path.exists(local_filepath):
            name_part, ext_part = os.path.splitext(base_filename)
            local_filepath = os.path.join(
                local_mailbox_path,
                f"{name_part}_{counter}{ext_part}"
            )
            counter += 1

        # Salva o arquivo .eml
        try:
            with open(local_filepath, "wb") as f:
                f.write(raw_email)
        except PermissionError as pe:
            logging.error(f"PermissionError ao gravar '{local_filepath}': {pe}", exc_info=True)
        except Exception as e:
            logging.error(f"Erro ao gravar '{local_filepath}': {e}", exc_info=True)

# PROCESSAMENTO DE UMA CONTA  
def archive_account(email_account: str):
    """
    Conecta ao servidor IMAP (com ou sem SSL), lista todas as pastas,
    e replica cada pasta localmente com o mesmo nome, salvando todos
    os e-mails. Tenta reconectar caso ocorram falhas de socket.
    """
    try:
        # Normaliza o endereço de e-mail para remover caracteres não-ASCII
        normalized_email = normalize_email(email_account)
        logging.info(f"Processando conta: {normalized_email}")

        # Conexão inicial utilizando o email normalizado
        mail = connect_imap_server(
            email_account=normalized_email,
            password=IMAP_PASSWORD,
            use_ssl=USE_SSL,
            host=IMAP_SERVER,
            port=IMAP_PORT
        )

        # Em vez de 'nonlocal mail', usamos um dicionário:
        mail_ref = {"mail": mail}

        # Diretório local para essa conta
        user_local_dir = os.path.join(MAILSTORE_HOME, get_local_username(normalized_email))
        create_folder(user_local_dir)

        # Lista todas as pastas do servidor
        status, mailbox_list = mail_ref["mail"].list()
        if status != "OK":
            logging.error(f"Não foi possível listar as pastas da conta {normalized_email}")
            mail_ref["mail"].logout()
            return

        for mailbox_info in mailbox_list:
            line = mailbox_info.decode("utf-8", errors="replace").strip()
            parts = line.rsplit(" ", 1)
            if len(parts) < 2:
                continue

            mailbox_name = parts[-1].strip('"')
            if mailbox_name == "." or mailbox_name == "":
                continue

            # Baixa a pasta, com reconexões se necessário
            download_mailbox(
                mail_ref=mail_ref,
                user_base_dir=user_local_dir,
                mailbox_name=mailbox_name,
                email_account=normalized_email,
                password=IMAP_PASSWORD,
                use_ssl=USE_SSL,
                host=IMAP_SERVER,
                port=IMAP_PORT,
                max_reconnects=MAX_RECONNECTS
            )

        mail_ref["mail"].logout()
        logging.info(f"Arquivamento concluído para {normalized_email}")
        time.sleep(2)

    except Exception as e:
        logging.error(f"Erro ao processar a conta {email_account}: {e}", exc_info=True)

# FUNÇÃO PRINCIPAL  
def main():
    init_logger()
    logging.info("Iniciando o arquivamento de e-mails (IMAP), com reconexão e retentativas...")

    for account in EMAIL_ACCOUNTS:
        archive_account(account)

    logging.info("Arquivamento de e-mails concluído.")

# EXECUÇÃO DO SCRIPT  
if __name__ == "__main__":
    main()