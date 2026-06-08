# Catálogo de Serviços Google Cloud Platform (GCP)

*Base de conhecimento curada para o agente comercial da Creattive.*

---

## Computação e Infraestrutura

### Cloud Run
Plataforma serverless para executar contêineres sem gerenciar servidores. Escala automaticamente para zero quando não há tráfego, cobrando apenas pelo uso. Ideal para APIs, microsserviços e aplicações web. Suporta qualquer linguagem via Docker.

### Compute Engine
Máquinas virtuais (VMs) de alta performance na infraestrutura do Google. Oferece centenas de tipos de máquina, incluindo opções com GPU e TPU. Ideal para workloads que exigem controle total do sistema operacional.

### Google Kubernetes Engine (GKE)
Serviço gerenciado de Kubernetes para orquestração de contêineres em escala. Automatiza deploy, escalonamento e operações de clusters. Ideal para aplicações distribuídas e microsserviços complexos.

### App Engine
Plataforma PaaS (Platform as a Service) para desenvolvimento e hospedagem de aplicações web sem gerenciamento de infraestrutura. Suporta Node.js, Python, Java, Go, PHP e Ruby nativamente.

### Cloud Functions
Funções serverless orientadas a eventos. Executa código em resposta a eventos do GCP (Pub/Sub, Cloud Storage, HTTP). Ideal para automações, integrações e processamento de eventos em tempo real.

---

## Dados e Analytics

### BigQuery
Data warehouse serverless e altamente escalável para análise de grandes volumes de dados. Executa consultas SQL em petabytes de dados em segundos. Integra com Looker, Data Studio e ferramentas de BI. Base para soluções de Data-Driven.

### Looker / Looker Studio
Plataforma de Business Intelligence (BI) e visualização de dados do Google. Looker é a versão enterprise com modelagem semântica (LookML); Looker Studio (antigo Data Studio) é gratuito para dashboards simples. Integra nativamente com BigQuery. Usado no produto Farol 360 da Creattive.

### Cloud Pub/Sub
Serviço de mensageria assíncrona e streaming de dados em tempo real. Desacopla produtores e consumidores de mensagens. Ideal para pipelines de dados, event-driven architecture e integração entre sistemas.

### Dataflow
Serviço gerenciado para processamento de dados em batch e streaming (ETL). Baseado no Apache Beam. Ideal para transformação e enriquecimento de dados antes de carregar no BigQuery.

### Dataproc
Serviço gerenciado de Apache Spark e Hadoop. Processa grandes volumes de dados de forma distribuída. Integra com Cloud Storage e BigQuery. Ideal para processamento de big data e machine learning em escala.

### Cloud Composer
Orquestração de pipelines de dados baseada no Apache Airflow. Gerencia dependências e agendamento de workflows de dados complexos.

---

## Inteligência Artificial e Machine Learning

### Vertex AI
Plataforma unificada de Machine Learning do Google Cloud. Permite treinar, implantar e gerenciar modelos de ML em escala. Inclui AutoML, pipelines de ML e integração com modelos Gemini. Base para soluções de IA da Creattive.

### Gemini API (Google AI)
API para acesso aos modelos Gemini (multimodal: texto, imagem, áudio, vídeo). Permite construir aplicações com IA generativa, chatbots, análise de documentos e automação inteligente. Usado no produto Creattive Minds.

### Document AI
Serviço de OCR e extração de dados estruturados de documentos (PDFs, imagens). Identifica e extrai campos de contratos, notas fiscais, formulários e outros documentos com alta precisão.

### Natural Language AI
Análise de texto com IA: sentimento, entidades, classificação de conteúdo e sintaxe. Ideal para análise de feedback de clientes, monitoramento de redes sociais e classificação automática de documentos.

### Translation AI
Tradução automática de alta qualidade para mais de 100 idiomas. Suporta tradução de documentos inteiros mantendo formatação.

---

## Segurança e Identidade

### Cloud IAM (Identity and Access Management)
Controle de acesso granular a recursos do GCP. Define quem pode fazer o quê em quais recursos. Essencial para governança de segurança em ambientes cloud.

### Secret Manager
Armazenamento seguro de credenciais, chaves de API e senhas. Integra com Cloud Run, GKE e outros serviços. Elimina segredos hardcoded no código.

### Cloud Armor
Proteção contra DDoS e ataques web (WAF). Regras baseadas em IP, geolocalização e padrões de ataque. Protege aplicações expostas na internet.

### Security Command Center
Plataforma centralizada de segurança e gerenciamento de riscos do GCP. Detecta vulnerabilidades, misconfigurações e ameaças em tempo real. Relacionado ao produto Sentinela Digital da Creattive.

### Cloud KMS (Key Management Service)
Gerenciamento de chaves criptográficas. Criptografia de dados em repouso e em trânsito. Conformidade com LGPD e regulamentações de proteção de dados.

---

## Armazenamento

### Cloud Storage
Armazenamento de objetos (blobs) altamente durável e escalável. Ideal para backups, arquivos estáticos, data lakes e armazenamento de mídia. Classes de armazenamento: Standard, Nearline, Coldline e Archive. Relacionado ao produto Data Safe Point da Creattive.

### Cloud SQL
Banco de dados relacional gerenciado (MySQL, PostgreSQL, SQL Server). Backups automáticos, alta disponibilidade e réplicas de leitura. Ideal para aplicações que precisam de banco relacional sem gerenciar servidores.

### Cloud Spanner
Banco de dados relacional distribuído globalmente, com escala horizontal e consistência forte. Ideal para aplicações financeiras e sistemas que precisam de escala global.

### Firestore
Banco de dados NoSQL orientado a documentos, serverless e em tempo real. Ideal para aplicações mobile, web e jogos que precisam de sincronização em tempo real.

### Bigtable
Banco de dados NoSQL de baixa latência para grandes volumes de dados. Ideal para séries temporais, IoT e aplicações de analytics em tempo real.

---

## Redes e Conectividade

### Cloud CDN
Rede de entrega de conteúdo global. Reduz latência servindo conteúdo estático de pontos próximos ao usuário. Integra com Cloud Load Balancing e Cloud Storage.

### Cloud Load Balancing
Balanceamento de carga global e regional para distribuir tráfego entre instâncias. Suporta HTTP/HTTPS, TCP e UDP. Alta disponibilidade automática.

### Cloud VPN / Cloud Interconnect
Conectividade segura entre infraestrutura on-premise e GCP. VPN para conexões menores; Interconnect para conexões dedicadas de alta largura de banda.

### VPC (Virtual Private Cloud)
Rede privada virtual isolada dentro do GCP. Controle total de roteamento, firewall e segmentação de rede. Base para qualquer arquitetura segura no GCP.

---

## Operações e Monitoramento

### Cloud Monitoring
Monitoramento de métricas, criação de dashboards e alertas para recursos do GCP e aplicações. Integra com Prometheus e outras ferramentas open source.

### Cloud Logging
Coleta, armazenamento e análise de logs de aplicações e infraestrutura. Retenção configurável e integração com BigQuery para análise avançada. Relacionado ao produto Guardião Creattive.

### Cloud Trace / Cloud Profiler
Rastreamento de latência e profiling de performance de aplicações distribuídas. Identifica gargalos e problemas de performance.

### Error Reporting
Detecção e agrupamento automático de erros em aplicações. Alertas em tempo real quando novos erros são detectados.

---

## DevOps e Desenvolvimento

### Cloud Build
Serviço de CI/CD (Integração e Entrega Contínua) gerenciado. Executa builds, testes e deploys automaticamente a partir de repositórios Git.

### Artifact Registry
Repositório gerenciado para armazenar imagens Docker, pacotes npm, Python, Maven e outros artefatos de build.

### Cloud Source Repositories
Repositório Git privado gerenciado pelo Google. Integra com Cloud Build para pipelines de CI/CD.

---

## Google Workspace (G Suite)

### Gmail, Drive, Meet, Docs, Sheets, Calendar
Suite de produtividade em nuvem do Google. A Creattive é parceira Google e oferece implementação, migração e suporte do Google Workspace para empresas.

---

## Programas de Parceria

### Google Cloud Partner
A Creattive é parceira oficial do Google Cloud, o que garante:
- Acesso antecipado a novos produtos e funcionalidades
- Suporte técnico especializado direto do Google
- Capacitação e certificações para a equipe técnica
- Descontos e créditos para clientes
- Elegibilidade para programas de co-venda com o Google
- Validação de especialização em soluções específicas (dados, segurança, infraestrutura)
