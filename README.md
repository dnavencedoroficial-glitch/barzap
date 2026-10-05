# BarZap — versão integrada para testes em nuvem

Painel por bar com login no servidor, produtos por categoria, mesas, garçons, pedidos, caixa diário, comandas e relatórios. Os registros permanecem no PostgreSQL; senhas são hashes e dados de cada bar são isolados por autorização no servidor.

## Rotina
1. Cadastre produtos, mesas e garçons. A aba QR Codes permite cadastrar as mesas de 1 a 50 sem alterar tokens existentes e gerar PDF das mesas selecionadas.
2. Abra o caixa e informe o troco diário. Todas as mesas fechadas ficam disponíveis. Pendências anteriores permanecem intactas.
3. O cliente entra pelo QR e faz pedidos com nome e celular; a identificação fica lembrada no mesmo navegador e sessão da mesa.
4. No atendimento, atribua o garçom e receba a mesa. Os 10% começam desmarcados. Adicione quantos pagamentos forem necessários em Pix, dinheiro, débito ou crédito. Os valores devem somar exatamente a conta.
5. A comanda fechada sai do atendimento e fica na aba Comandas fechadas, com impressão, data/hora de abertura, fechamento, garçom, produtos e pagamentos.
6. Feche o caixa informando dinheiro contado incluindo troco. Se houver consumo não recebido, é exigida a senha do dono do bar ou administrador e um motivo. O relatório registra quem autorizou, quem operou e as mesas pendentes. Mesas vazias fecham automaticamente. As pendências não contam como valores recebidos.
7. Consulte Fechamentos de caixa com valores separados, troco, taxa por garçom e diferença entre dinheiro esperado e contado. Os relatórios têm filtros de data e impressão.

Pagamentos são registros de recebimentos feitos pelo bar. Este código não realiza cobranças, transferências ou integração com maquininhas. A cobrança automática da assinatura ainda não foi implementada. Validade: 30 dias e mais 5 dias de tolerância, controlados no servidor; administrador pode renovar manualmente.

## Configuração
Python 3.12 e dependências de requirements.txt. Produção: APP_ENV=production, SECRET_KEY aleatória com ao menos 32 caracteres, DATABASE_URL PostgreSQL e TRUSTED_HOSTS com o domínio do aplicativo. Dockerfile inicia Gunicorn com um worker. A criação inicial das tabelas no PostgreSQL usa trava de transação para evitar inicializações simultâneas.

No primeiro início, ADMIN_EMAIL e ADMIN_PASSWORD (ao menos 10 caracteres) podem criar o administrador. Contas existentes não são sobrescritas. Depois de confirmar o acesso, remova ADMIN_PASSWORD do painel de ambiente. Não coloque segredos no GitHub. O comando Flask create-admin continua disponível para instalações privadas.

Desenvolvimento: use SECRET_KEY de testes e DATABASE_URL SQLite em pasta de trabalho; execute `python -m unittest discover -p "test_*.py"`. O servidor Flask de desenvolvimento não é a configuração de produção.

## Dados e validação
A integração adiciona novas tabelas. Não remove ou renomeia as tabelas anteriores de bares, usuários, produtos, mesas ou pedidos. Pedidos anteriores da sessão aberta podem ser recebidos no primeiro caixa. Dados do antigo protótipo localStorage não são importados automaticamente.

20 testes locais verificaram autenticação, privacidade, isolamento, preços, tolerância, persistência, caixa, pagamentos divididos, taxa opcional, pendências, diferença de caixa, recibos, proteção contra fechamento duplicado e PDFs. Um fluxo local com dados fictícios foi verificado na tela. PDF de 50 mesas foi gerado com 9 páginas e inspecionado visualmente. A atualização financeira ainda precisa ser validada no PostgreSQL hospedado após publicação.

Antes do uso comercial: implementar backups e migrações versionadas, recuperação de senha, cobrança de assinatura e revisão de segurança/carga. O controle de tentativas está na memória do worker. O banco gratuito do Render expira; sua capacidade e disponibilidade devem ser consideradas no uso definitivo.
