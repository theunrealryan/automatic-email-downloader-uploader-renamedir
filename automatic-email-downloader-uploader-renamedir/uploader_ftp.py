from ftplib import FTP_TLS
import os

# Credenciais e configurações
FTP_HOST = ""
FTP_USER = ""
FTP_PASS = ""
REMOTE_PATH = ""  # Diretório de destino no servidor
LOCAL_FOLDER = ""  # Pasta local onde os arquivos estão
CHUNK_SIZE = 1024 * 1024 * 5  # 5MB (tentar reduzir se 10MB estiver causando problemas)

# Lista dos arquivos ZIP a serem enviados
FILE_LIST = [
    ""
]

def upload_file(ftp, local_file):
    """Realiza o upload de um único arquivo via FTP em chunks."""
    file_size = os.path.getsize(local_file)
    uploaded_size = 0

    print(f"\nArquivo: {os.path.basename(local_file)}")
    print(f"Tamanho local: {file_size} bytes")

    # Tenta verificar se o arquivo já existe no servidor para retomar upload (se aplicável)
    try:
        remote_size = ftp.size(os.path.basename(local_file))
        uploaded_size = remote_size if remote_size is not None else 0
        print(f"Tamanho remoto antes do upload: {uploaded_size} bytes")
    except Exception as e:
        print("Arquivo remoto não encontrado, iniciando upload do zero.")
        uploaded_size = 0

    with open(local_file, "rb") as f:
        f.seek(uploaded_size)  # Retoma upload, se necessário

        def upload_chunk(data):
            nonlocal uploaded_size
            uploaded_size += len(data)
            print(f"Uploaded: {uploaded_size / file_size * 100:.2f}%", end="\r")

        try:
            ftp.storbinary(f"STOR {os.path.basename(local_file)}", f, CHUNK_SIZE, upload_chunk)
        except Exception as e:
            print(f"\nErro durante o upload de {os.path.basename(local_file)}: {e}")

    try:
        final_size = ftp.size(os.path.basename(local_file))
        print(f"\nTamanho remoto após o upload: {final_size} bytes")
        if final_size == file_size:
            print(f"Upload de {os.path.basename(local_file)} concluído com sucesso.")
        else:
            print(f"O arquivo remoto {os.path.basename(local_file)} não corresponde ao tamanho local.")
    except Exception as e:
        print(f"Não foi possível verificar o tamanho do arquivo remoto {os.path.basename(local_file)}: {e}")

def upload_file_list():
    """Conecta ao FTP, percorre a lista de arquivos e realiza o upload de cada um."""
    ftp = FTP_TLS(FTP_HOST)
    ftp.login(FTP_USER, FTP_PASS)
    ftp.prot_p()  # Ativa transferência de dados segura
    ftp.set_pasv(True)  # Modo passivo, se necessário
    ftp.cwd(REMOTE_PATH)  # Muda para o diretório de destino

    for filename in FILE_LIST:
        local_file = os.path.join(LOCAL_FOLDER, filename)
        if os.path.exists(local_file):
            upload_file(ftp, local_file)
        else:
            print(f"\nArquivo não encontrado: {local_file}")

    ftp.quit()
    print("\nTodos os uploads foram concluídos.")

if __name__ == "__main__":
    upload_file_list()
