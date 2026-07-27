# API ANEEL — Indicadores de Continuidade Coletivos

Esta é uma API intermediária desenvolvida em Python (FastAPI) para facilitar a ingestão de dados abertos da ANEEL diretamente no **Power BI Online**, contornando limitações de timeout, memória e suporte a scripts Python na nuvem da Microsoft.

A API extrai a base completa de **Indicadores de Continuidade Coletivos (2020-2029)**.

## 🚀 O Problema Resolvido
A base original da ANEEL é fornecida em um arquivo `.zip` pesado. O Power BI (especialmente o Serviço Online) frequentemente apresenta erros ao tentar baixar e descompactar arquivos grandes em memória (Linguagem M) ou ao rodar scripts Python não suportados pela nuvem. 

Esta API resolve o problema servindo como uma **ponte otimizada**:
1. Ela baixa o ZIP de forma resiliente.
2. Extrai o arquivo CSV fisicamente no disco do servidor.
3. Transmite o CSV limpo diretamente para o Power BI utilizando a função `FileResponse`, resultando em um consumo de Memória RAM próximo a zero.

## ⚙️ Estrutura de Cache
Para evitar bloqueios por excesso de requisições no servidor da ANEEL e acelerar o carregamento dos painéis, a API utiliza um sistema de **cache em disco**:
* O arquivo CSV fica salvo no servidor por **24 horas**.
* Qualquer requisição feita dentro desse período retorna o arquivo instantaneamente do disco local.
* Após 24 horas, a API descarta o arquivo velho e busca a base atualizada na ANEEL.

## 🌐 Endpoints Disponíveis

| Endpoint | Método | Descrição |
|---|---|---|
| `/` | GET | Página de boas-vindas e verificação de status online da API. |
| `/dados` | GET | **Principal:** Retorna o arquivo CSV completo. Endpoint a ser conectado no Power BI. |
| `/status` | GET | Retorna um JSON detalhado com a saúde da API, validade do cache e tamanho do arquivo em disco. |

## 📊 Como consumir no Power BI

1. No Power BI Desktop, clique em **Obter Dados** > **Web**.
2. Insira a URL da API apontando para o endpoint de dados:
   ```text
   [https://NOME-DO-SEU-SERVICO.onrender.com/dados](https://NOME-DO-SEU-SERVICO.onrender.com/dados)
