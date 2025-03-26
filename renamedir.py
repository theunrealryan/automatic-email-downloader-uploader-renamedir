import os
import shutil

# Lista de diretórios base
base_paths = [
    
]

# Conjunto de nomes (após remover "INBOX.") que deverão receber o prefixo "."
dot_folders = {"Drafts", "Junk", "Sent", "spam", "Trash", "Archive"}

def safe_move(src, dst):
    """
    Move o arquivo de src para dst. Se já existir um arquivo com o mesmo nome em dst,
    adiciona um sufixo numérico para evitar sobrescrever.
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

# Itera sobre cada diretório base da lista
for base_path in base_paths:
    # Itera sobre todos os itens no diretório base
    for folder in os.listdir(base_path):
        old_path = os.path.join(base_path, folder)

        # Processa apenas diretórios
        if os.path.isdir(old_path):

            # Caso seja "INBOX", renomeia para "cur" (sem criar subpasta "cur" dentro)
            if folder == "INBOX":
                new_name = "cur"
                new_path = os.path.join(base_path, new_name)
                os.rename(old_path, new_path)
                continue  # Pula para o próximo diretório

            # Se o diretório começar com "INBOX.", remove essa parte
            if folder.startswith("INBOX."):
                new_name = folder.replace("INBOX.", "", 1)
                # Se o nome resultante estiver no conjunto, adiciona o ponto na frente
                if new_name in dot_folders:
                    new_name = "." + new_name
            else:
                new_name = folder  # Mantém o nome original caso não contenha "INBOX."

            new_path = os.path.join(base_path, new_name)

            # Renomeia o diretório, se necessário
            if old_path != new_path:
                os.rename(old_path, new_path)

            # Para os diretórios convertidos (exceto o "cur" resultante de INBOX):
            # cria a subpasta "cur" e move os arquivos que estiverem na raiz para ela.
            if new_name != "cur":
                cur_subfolder = os.path.join(new_path, "cur")
                os.makedirs(cur_subfolder, exist_ok=True)

                # Percorre os itens presentes na raiz do diretório recém-renomeado
                # Observação: se houver subpastas (como uma eventual pasta "cur" já existente),
                # elas não serão afetadas.
                for item in os.listdir(new_path):
                    item_path = os.path.join(new_path, item)
                    # Move apenas os arquivos; diretórios (como a própria pasta "cur") são ignorados.
                    if os.path.isfile(item_path):
                        destination = os.path.join(cur_subfolder, item)
                        safe_move(item_path, destination)

print("Conversão de diretórios concluída!")
