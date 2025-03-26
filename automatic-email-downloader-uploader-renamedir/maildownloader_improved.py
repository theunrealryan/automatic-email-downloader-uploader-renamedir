import imaplib
import email
import os
import time
import logging
import re
import socket
import shutil
import unicodedata  # para normalização Unicode
from email.header import decode_header
from logging.handlers import RotatingFileHandler

# CONFIGURAÇÃO GLOBAL DO SOCKET
socket.setdefaulttimeout(120)

# CONFIGURAÇÃO DO SERVIDOR IMAP
IMAP_SERVER = ""  # Endereço do servidor IMAP
IMAP_PORT = 143                  # Porta padrão IMAP (143 para STARTTLS, 993 para SSL)
USE_SSL = False                  # Se True, usará IMAP4_SSL; caso contrário, IMAP4 normal
IMAP_PASSWORD = ""      # Senha de acesso

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


# INICIALIZAÇÃO DO LOG

def init_logger():
    """
    Configura o logger global com StreamHandler e RotatingFileHandler,
    removendo handlers existentes para evitar duplicações.
    """
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)
    while logger.handlers:
        logger.removeHandler(logger.handlers[0])
    log_format = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(log_format)
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
    """
    return email_address.split('@')[0]

def create_folder(path: str):
    """
    Cria um diretório local (sem erro se já existir).
    """
    try:
        os.makedirs(path, exist_ok=True)
    except Exception as e:
        logging.error(f"Não foi possível criar a pasta '{path}': {e}", exc_info=True)

def decode_subject(subject: str) -> str:
    """
    Decodifica o cabeçalho 'Subject' (RFC 2047).
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
    Conecta ao servidor IMAP e faz login na conta especificada.
    Realiza uma normalização do e-mail, removendo caracteres indesejados (como soft hyphen).
    """
    # Normaliza o endereço de e-mail para remover caracteres indesejados
    normalized_email = unicodedata.normalize('NFKC', email_account)
    # Remove explicitamente o soft hyphen
    normalized_email = normalized_email.replace('\xad', '')
    logging.info(f"Tentando login com: {normalized_email}")
    if use_ssl:
        mail_conn = imaplib.IMAP4_SSL(host, port)
    else:
        mail_conn = imaplib.IMAP4(host, port)
    mail_conn.login(normalized_email, password)
    return mail_conn

def safe_move(src: str, dst: str):
    """
    Move o arquivo de src para dst. Se já existir um arquivo com o mesmo nome em dst,
    adiciona um sufixo numérico para evitar sobrescrita.
    """
    if os.path.exists(dst):
        base, ext = os.path.splitext(os.path.basename(dst))
        counter = 1
        new_dst = os.path.join(os.path.dirname(dst), f"{base}_{counter}{ext}")
        while os.path.exists(new_dst):
            counter += 1
            new_dst = os.path.join(os.path.dirname(dst), f"{base}_{counter}{ext}")
        dst = new_dst
    shutil.move(src, dst)

def restructure_mailbox_dir(local_mailbox_path: str):
    """
    Para pastas locais cujo nome não seja "cur":
      - Cria a subpasta "cur".
      - Move os arquivos que estão na raiz para a subpasta "cur".
    """
    if os.path.basename(local_mailbox_path) == "cur":
        return
    cur_subfolder = os.path.join(local_mailbox_path, "cur")
    create_folder(cur_subfolder)
    for item in os.listdir(local_mailbox_path):
        item_path = os.path.join(local_mailbox_path, item)
        if os.path.isfile(item_path):
            destination = os.path.join(cur_subfolder, item)
            safe_move(item_path, destination)

def fetch_email_with_retry(mail_ref, email_id, mailbox_name,
                           fetch_retries, fetch_delay, reconnect_callback):
    """
    Executa FETCH para um email_id, com retentativas e reconexões em caso de falha.
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
            reconnect_ok = reconnect_callback()
            if not reconnect_ok:
                break
            time.sleep(fetch_delay)
        except Exception as e:
            logging.warning(
                f"Erro inesperado na tentativa {attempt+1} de {fetch_retries} para e-mail ID {email_id.decode('utf-8')}: {e}"
            )
            time.sleep(fetch_delay)
    return None, None

def download_mailbox(mail_ref, user_base_dir: str, imap_mailbox_name: str, local_mailbox_name: str,
                     email_account: str, password: str,
                     use_ssl: bool, host: str, port: int,
                     max_reconnects: int):
    """
    Seleciona a pasta IMAP 'imap_mailbox_name' e baixa todos os e-mails para o diretório
    local 'local_mailbox_name'. Em seguida, reestrutura a pasta criando a subpasta 'cur'.
    """
    reconnect_count = [0]

    def reconnect_callback():
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
            status, _ = new_mail.select(imap_mailbox_name)
            if status != "OK":
                logging.error(f"Não foi possível selecionar a pasta '{imap_mailbox_name}' após reconexão.")
                return False
            mail_ref["mail"] = new_mail
            return True
        except Exception as e:
            logging.error(f"Falha ao reconectar: {e}", exc_info=True)
            return False

    status, _ = mail_ref["mail"].select(imap_mailbox_name)
    if status != "OK":
        logging.error(f"Não foi possível selecionar a pasta '{imap_mailbox_name}'.")
        return

    local_mailbox_path = os.path.join(user_base_dir, local_mailbox_name)
    create_folder(local_mailbox_path)

    status, messages = mail_ref["mail"].search(None, "ALL")
    if status != "OK":
        logging.error(f"Erro ao buscar e-mails na pasta '{imap_mailbox_name}'.")
        return

    email_ids = messages[0].split()
    logging.info(f"Baixando {len(email_ids)} e-mails de '{imap_mailbox_name}' (conta: {email_account})...")

    for email_id in email_ids:
        status, data = fetch_email_with_retry(
            mail_ref=mail_ref,
            email_id=email_id,
            mailbox_name=imap_mailbox_name,
            fetch_retries=FETCH_RETRIES,
            fetch_delay=FETCH_DELAY,
            reconnect_callback=reconnect_callback
        )
        if status != "OK" or data is None:
            logging.warning(
                f"Não foi possível buscar o e-mail ID {email_id.decode('utf-8')} na pasta '{imap_mailbox_name}'."
            )
            continue

        raw_email = data[0][1]
        msg = email.message_from_bytes(raw_email)

        subject = msg.get("subject", "sem_assunto")
        subject = decode_subject(subject)
        sanitized_subject = sanitize_filename(subject)

        base_filename = f"{sanitized_subject}_{email_id.decode('utf-8')}.eml"
        local_filepath = os.path.join(local_mailbox_path, base_filename)

        counter = 1
        while os.path.exists(local_filepath):
            name_part, ext_part = os.path.splitext(base_filename)
            local_filepath = os.path.join(local_mailbox_path, f"{name_part}_{counter}{ext_part}")
            counter += 1

        try:
            with open(local_filepath, "wb") as f:
                f.write(raw_email)
        except PermissionError as pe:
            logging.error(f"PermissionError ao gravar '{local_filepath}': {pe}", exc_info=True)
        except Exception as e:
            logging.error(f"Erro ao gravar '{local_filepath}': {e}", exc_info=True)

    restructure_mailbox_dir(local_mailbox_path)

def archive_account(email_account: str):
    """
    Conecta ao servidor IMAP, lista as pastas e, para cada uma, realiza o download dos e-mails,
    aplicando a lógica de renomeação e estruturação de diretórios.
    
    Mantém o padrão previamente estabelecido:
      - Se a pasta for "INBOX", armazena como "cur".
      - Se iniciar com "INBOX.", remove o prefixo; se o nome resultante estiver em dot_folders,
        adiciona o ponto à esquerda.
      - Para as demais pastas, se o nome não começar com '.', adiciona o ponto; caso contrário, mantém o original.
    """
    try:
        logging.info(f"Processando conta: {email_account}")

        mail = connect_imap_server(
            email_account=email_account,
            password=IMAP_PASSWORD,
            use_ssl=USE_SSL,
            host=IMAP_SERVER,
            port=IMAP_PORT
        )
        mail_ref = {"mail": mail}

        user_local_dir = os.path.join(MAILSTORE_HOME, get_local_username(email_account))
        create_folder(user_local_dir)

        status, mailbox_list = mail_ref["mail"].list()
        if status != "OK":
            logging.error(f"Não foi possível listar as pastas da conta {email_account}")
            mail_ref["mail"].logout()
            return

        dot_folders = {"Drafts", "Junk", "Sent", "spam", "Trash", "Archive"}

        for mailbox_info in mailbox_list:
            line = mailbox_info.decode("utf-8", errors="replace").strip()
            parts = line.rsplit(" ", 1)
            if len(parts) < 2:
                continue

            raw_mailbox_name = parts[-1].strip('"')
            if raw_mailbox_name == "" or raw_mailbox_name == ".":
                continue

            if raw_mailbox_name == "INBOX":
                local_mailbox_name = "cur"
            elif raw_mailbox_name.startswith("INBOX."):
                local_mailbox_name = raw_mailbox_name.replace("INBOX.", "", 1)
                if local_mailbox_name in dot_folders:
                    local_mailbox_name = "." + local_mailbox_name
            else:
                if not raw_mailbox_name.startswith("."):
                    local_mailbox_name = "." + raw_mailbox_name
                else:
                    local_mailbox_name = raw_mailbox_name

            download_mailbox(
                mail_ref=mail_ref,
                user_base_dir=user_local_dir,
                imap_mailbox_name=raw_mailbox_name,
                local_mailbox_name=local_mailbox_name,
                email_account=email_account,
                password=IMAP_PASSWORD,
                use_ssl=USE_SSL,
                host=IMAP_SERVER,
                port=IMAP_PORT,
                max_reconnects=MAX_RECONNECTS
            )

        mail_ref["mail"].logout()
        logging.info(f"Arquivamento concluído para {email_account}")
        time.sleep(2)

    except Exception as e:
        logging.error(f"Erro ao processar a conta {email_account}: {e}", exc_info=True)

def main():
    init_logger()
    logging.info("Iniciando o arquivamento de e-mails (IMAP) com reconexão, retentativas e diretórios aprimorados...")
    for account in EMAIL_ACCOUNTS:
        archive_account(account)
    logging.info("Arquivamento de e-mails concluído.")

if __name__ == "__main__":
    main()