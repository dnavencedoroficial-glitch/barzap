# BarZap — base de servidor para nuvem

Esta pasta é uma etapa nova, separada do protótipo completo anterior. Tem banco de dados e autenticação no servidor, não senhas no JavaScript.

## O que está implementado e testado

Login com hash de senha, sessão HTTPOnly e proteção CSRF; administrador geral e responsável limitado ao bar; cadastro e ordem de liberação de bares; início na data atual, 30 dias de assinatura e 5 dias de tolerância validados no servidor; produtos com categoria/descrição/valor; mesas com link próprio; abertura de mesas; pedidos públicos com nome e telefone; valores calculados a partir dos preços do banco; identificador para evitar pedidos duplicados em novas tentativas; consulta de pedidos em outra sessão e atualização de status. O painel consulta o servidor a cada 3 segundos e pode emitir alerta sonoro. O banco aceita SQLite para desenvolvimento e PostgreSQL para produção.

## O que ainda não está migrado

Caixa, troco, fechamento de comandas, pagamentos divididos, 10% por garçom, relatórios, impressão e geração dos 50 QR Codes continuam no protótipo anterior. A tela desta pasta é para validar o servidor e o fluxo de pedidos; não substitui ainda todas as telas do BarZap completo. Não há cobrança automática, conta de hospedagem, domínio ou publicação criados. A renovação administrativa atual é manual. Não importe credenciais ou saldos do protótipo automaticamente.

## Testar localmente

Instale Python 3.12, crie um ambiente virtual nesta pasta e instale requirements.txt. No Windows, gunicorn não é instalado; o teste pode usar Flask apenas na rede local. Configure as variáveis no PowerShell (não envie os valores para outras pessoas):

```powershell
$env:SECRET_KEY = (python -c "import secrets; print(secrets.token_hex(32))")
$env:ADMIN_EMAIL = 'Dnadigital.vca@gmail.com'
$taskAdminSecret = Read-Host 'Senha inicial do administrador' -AsSecureString
$env:ADMIN_PASSWORD = [System.Net.NetworkCredential]::new('', $taskAdminSecret).Password
python -m flask --app server:create_app create-admin
Remove-Item Env:ADMIN_PASSWORD
python -m flask --app server:create_app run --host 0.0.0.0 --port 8000
```

A senha é armazenada apenas como hash no banco. Escolha uma nova senha para produção porque a senha do protótipo já apareceu no código entregue. Não coloque a senha no repositório. A senha digitada fica oculta no terminal. O banco SQLite local é criado quando o servidor inicia, não é enviado no pacote.

Abra http://localhost:8000, faça login e cadastre o primeiro bar. No painel do bar, cadastre produto e mesa, disponibilize as mesas e abra o link de atendimento em outro navegador ou celular conectado à rede. Cadastros reais e pedidos compartilham o mesmo banco no servidor. Ative som no painel para ouvir novos pedidos. Para testar: `python -m unittest test_server.py`.

## Preparação para hospedagem

No Render, um Web Service executaria esta pasta com build `pip install -r requirements.txt` e start `gunicorn --workers 2 --bind 0.0.0.0:$PORT wsgi:app`, com um banco PostgreSQL. Configure SECRET_KEY, DATABASE_URL, APP_ENV=production e TRUSTED_HOSTS no painel do serviço, conforme .env.example. Não copie valores de exemplo literalmente. HTTPS é fornecido pela hospedagem; domínio e custos precisam ser aprovados antes da contratação/publicação. O Dockerfile é uma alternativa de empacotamento; não foi executado neste ambiente.

Crie o administrador uma única vez com o comando create-admin em ambiente privado. Evite deixar ADMIN_PASSWORD configurada após a criação. Não publique o protótipo antigo com suas senhas de demonstração. Nenhuma chave de pagamento foi configurada aqui.

## Limites de operação

O bloqueio de login por tentativas usa memória do processo e precisa de armazenamento compartilhado antes de produção com múltiplos workers. A base usa create_all para criação inicial; migrações versionadas, backups, recuperação de senha, revisão de segurança e testes de concorrência/carga ainda precisam ser implementados antes do uso comercial. Os testes foram feitos com SQLite e clientes HTTP internos do Flask; PostgreSQL e hospedagem externa não foram testados nesta etapa. Nenhum servidor público foi iniciado.

Referências: https://flask.palletsprojects.com/en/stable/deploying/gunicorn/ e https://render.com/docs/web-services.

Validação: 10 testes passaram (autenticação, hash, CSRF, isolamento, privacidade, pedidos, preços, tolerância, renovação e persistência). Sintaxe da interface validada. PostgreSQL e hospedagem externa ainda não foram testados.
