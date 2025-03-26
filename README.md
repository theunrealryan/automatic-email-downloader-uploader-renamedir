# Automação de Download e Upload de Webmails Institucionais

Este repositório contém um conjunto de scripts em Python desenvolvidos para automatizar o processo de download e upload de webmails institucionais. A solução visa facilitar a integração, o backup e o arquivamento dos e-mails, garantindo robustez, escalabilidade e segurança na transferência e armazenamento dos dados.

## Visão Geral

A proposta deste projeto é oferecer uma abordagem modular e confiável para a automação de processos envolvendo o acesso aos servidores de e-mail via protocolo IMAP e a transferência de arquivos utilizando FTP/FTPS. Os scripts permitem a conexão segura aos servidores, com o uso de bibliotecas nativas do Python, como **imaplib** e **ftplib**, e implementam mecanismos de reconexão, retentativas e logs detalhados para monitoramento e auditoria das operações realizadas. Essa solução é aplicável a diversos cenários, incluindo o arquivamento legal de comunicações em órgãos públicos, backup corporativo e a automação de processos em ambientes com múltiplas contas de e-mail.

## Funcionalidades

- **Download Automático de E-mails via IMAP**:  
  Os scripts realizam a conexão ao servidor de e-mail utilizando os protocolos IMAP (com ou sem SSL/TLS), buscando e armazenando os e-mails em diretórios locais estruturados de acordo com a caixa postal original. São implementadas estratégias para a normalização e sanitização de nomes de arquivos e diretórios, evitando a sobrescrição de e-mails e garantindo a integridade dos dados.

- **Upload Seguro de Arquivos via FTP/FTPS**:  
  O processo de upload é realizado de forma segmentada (em chunks), o que possibilita a retomada do envio em caso de interrupções. O uso de **FTP_TLS** assegura que a transferência seja realizada de maneira criptografada, protegendo os dados sensíveis durante o transporte.

- **Reestruturação e Organização de Diretórios**:  
  Scripts auxiliares realizam a renomeação e reestruturação de pastas, convertendo nomes conforme convenções estabelecidas (por exemplo, renomeando "INBOX" para "cur" e adicionando prefixos em pastas específicas), o que facilita a navegação e o gerenciamento dos e-mails arquivados.

- **Monitoramento e Log**:  
  A implementação de logs através do módulo **logging** com suporte a rotação de arquivos permite a rastreabilidade e auditoria das operações, assegurando que quaisquer erros ou falhas sejam devidamente registrados e analisados para melhorias contínuas.

## Estrutura do Repositório

- **maildownloader.py** e **maildownloader_improved.py**:  
  Scripts responsáveis pelo download dos e-mails a partir de contas especificadas, utilizando conexões IMAP com suporte a reconexões e retentativas em caso de falhas.

- **uploader_ftp.py**:  
  Script dedicado ao upload dos arquivos para servidores FTP/FTPS, utilizando transferência segmentada para assegurar a integridade dos arquivos enviados.

- **renamedir.py**:  
  Script para a reorganização dos diretórios locais, renomeando pastas conforme a convenção definida e criando subpastas para a correta separação dos arquivos.

## Requisitos e Instalação

Para executar os scripts, é necessário ter o Python 3 instalado no ambiente. As bibliotecas utilizadas são parte da biblioteca padrão do Python, não sendo necessário instalar dependências adicionais para a execução dos códigos. Recomenda-se, entretanto, a criação de um ambiente virtual para isolar as dependências do projeto.

```bash
# Criação e ativação do ambiente virtual (opcional)
python3 -m venv venv
source venv/bin/activate   # No Linux/Mac
venv\Scripts\activate      # No Windows

# Clonar o repositório
git clone <URL-do-repositório>
cd <nome-do-repositório>
```

## Configuração

Antes de executar os scripts, é necessário configurar os parâmetros essenciais, tais como:

- **Servidor IMAP/FTP**: Endereço, porta, usuário e senha.
- **Diretórios Locais**: Caminhos para armazenamento dos e-mails e arquivos a serem enviados.
- **Parâmetros de Conexão**: Timeouts, número de retentativas, e configuração de segurança (SSL/TLS).

Os parâmetros devem ser definidos diretamente nos arquivos de configuração de cada script (comentários presentes no código auxiliam na compreensão e ajuste dos parâmetros).

## Execução

Após a configuração, os scripts podem ser executados individualmente conforme a necessidade:

- **Para download dos e-mails:**

  ```bash
  python maildownloader.py
  # ou
  python maildownloader_improved.py
  ```

- **Para upload dos arquivos:**

  ```bash
  python uploader_ftp.py
  ```

- **Para reestruturação dos diretórios:**

  ```bash
  python renamedir.py
  ```

## Boas Práticas

- **Segurança das Credenciais**: Utilize variáveis de ambiente ou ferramentas de gerenciamento de segredos para evitar a exposição de senhas e informações sensíveis nos arquivos de configuração.
- **Controle de Versões**: Recomenda-se utilizar um sistema de versionamento (como Git) para acompanhar as alterações nos scripts e facilitar o gerenciamento de versões.
- **Testes e Homologação**: Realize testes em ambientes de homologação antes de aplicar as alterações em produção, garantindo que todas as configurações estejam corretas e que o fluxo de trabalho seja executado conforme o esperado.

## Referências

- **RFC 3501** – *Internet Message Access Protocol - Version 4rev1* (Crispin, 2003).  
- **RFC 959** – *File Transfer Protocol (FTP)* (Postel, 1985).  
- **Python Software Foundation** – [Documentação imaplib](https://docs.python.org/3/library/imaplib.html) e [Documentação ftplib](https://docs.python.org/3/library/ftplib.html).  
- Chaparro, E. (2021). *Enterprise Email Management: Best Practices*. Journal of Computer Science.

---

Este repositório visa oferecer uma solução abrangente e robusta para o gerenciamento automatizado de e-mails institucionais, aliando práticas de segurança, escalabilidade e monitoramento contínuo, essenciais para a transformação digital e a governança de TI.
