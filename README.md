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


## Fotos do cardápio
O catálogo revisado reconhece Amstel 600 ml (incluindo o cadastro amsrel confirmado pelo dono), Brahma 600 ml e 1 litro, Original 1 litro e os dois petiscos cadastrados. A associação usa nome e categoria e mantém preços, produtos e dados de cada bar. Novos produtos sem foto fornecida buscam automaticamente no Openverse quando não estão no catálogo. Apenas títulos compatíveis e licenças que permitem uso comercial e alteração são aceitos. Sem resultado, o produto é salvo e o painel informa que é necessário escolher uma foto ou buscar novamente. As imagens são servidas localmente; o visitante não envia informações a sites externos para carregar fotos. Créditos e licenças ficam acessíveis no cardápio. Fotos dos petiscos são ilustrativas, redimensionadas, e podem ter enquadramento na tela.

Batata frita: City Foodsters, Wikimedia Commons, CC BY 2.0. Batata com bacon e cheddar: Ser Amantio di Nicolao, Wikimedia Commons, CC BY-SA 3.0 (a imagem mantém esta licença). Cervejas: imagens de embalagem publicadas por Amstel Brasil, Rizatti/Brahma e Supermercado Bresciani/Original; marcas e imagens pertencem a seus respectivos titulares. Fontes completas no arquivo menu_images.py.


Fotos automáticas ou fornecidas pelo bar são normalizadas como JPEG, sem metadados pessoais, e persistidas na tabela adicional product_photos do PostgreSQL. Nenhum pedido, cliente, telefone, e-mail ou nome de bar é enviado para buscar fotos; somente o nome do produto é usado na busca do Openverse. A consulta tem limite de tempo, tamanho e fonte. Não consulta nem baixa URLs fornecidas por usuários. O painel permite trocar a foto e enviar JPG, PNG ou WebP; o navegador reduz o arquivo antes do envio. A imagem buscada é ilustrativa e deve ser conferida pelo bar. Falha, limite ou indisponibilidade do provedor não impede o cadastro. Novas buscas precisam de internet no servidor.

## Catálogo inicial de bebidas

Cada bar existente e novo recebe 61 bebidas revisadas com imagens locais: 31 refrigerantes e 30 variantes de cervejas, nas embalagens confirmadas. A tabela adicional product_presets marca cada importação por bar; reiniciar não duplica nem restaura produtos excluídos. Correspondências existentes preservam nome, preço e ID. Novos itens começam com preço pendente (zero interno), ficam ocultos do cardápio público e são rejeitados em pedidos até o preço positivo ser salvo na aba Produtos. Preços podem ser editados individualmente com autorização do respectivo bar. Fontes e créditos em starter_catalog.json; imagens de embalagens pertencem aos respectivos titulares. Não importa dados de outros bares nem altera comandas.

## Estoque

A aba Estoque permite definir contagem atual e registrar compras, com motivo, operador e histórico das últimas 100 movimentações. Quantidades iniciais não são inventadas: produtos sem contagem ficam Não informado e não recebem baixa até a primeira contagem. Novos pedidos descontam unidades na mesma transação; reenvios não dão baixa duplicada. Saldo abaixo de 6 gera sugestão para completar 6, incluindo saldo zero ou negativo. O saldo não bloqueia pedidos: valores negativos sinalizam divergência que deve ser conferida. Contagens exigem inteiros não negativos. Nenhum pedido anterior à implantação é descontado retroativamente. Trava por bar serializa ajustes e pedidos. Tabelas adicionais product_stock e stock_movements; autorização por bar e CSRF, estoque não é publicado no cardápio do cliente.

## Troco da comanda

Recebimentos em dinheiro permitem valor entregue acima do saldo, com prévia do troco. Pix e cartões não podem exceder o total da conta. O servidor valida os totais e armazena valor entregue, troco e pagamento líquido no recibo. Em pagamentos divididos, o troco é abatido das linhas em dinheiro, da última para a primeira. O caixa soma apenas valores líquidos e informa o troco devolvido aos clientes. Recibos antigos permanecem compatíveis.

## Acesso e senhas

O cliente troca sua própria senha informando a senha atual, a nova e a confirmação. O administrador define a senha inicial ao liberar um bar e pode redefinir a senha de um usuário daquele bar em Acesso e senhas. Não há consulta de senha: somente hashes são armazenados. A tabela credential_versions invalida outras sessões após alteração ou redefinição; a sessão que troca sua própria senha continua válida. Novas senhas de troca/redefinição exigem 10 a 200 caracteres. PDF de controle contém apenas dados informados pelo proprietário e campos preenchíveis; não é incluído no código publicado nem no ZIP de instalação.
