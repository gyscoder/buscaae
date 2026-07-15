# 📚 Book Dork Search API v2.0

API de código aberto para busca de documentos públicos (PDF, EPUB, MOBI) usando operadores de busca avançados (Google Dorks) com segurança, desempenho e observabilidade aprimorados.

## ✨ Novidades na v2.0

- **🔒 Segurança Aprimorada**: Limitação de taxa, validação/sanitização de entrada, restrições de CORS, execução Docker não-root
- **⚡ Otimização de Desempenho**: Cache em memória com TTL para reduzir chamadas externas
- **👁️‍🗨️ Observabilidade Melhorada**: Logging estruturado (`structlog`), endpoint de health check, métricas detalhadas
- **🛠️ Melhor Manutenibilidade**: Configuração centralizada, código modular, type hints em todo o código
- **🐳 Docker Pronto para Produção**: Imagem otimizada com boas práticas de segurança
- **📖 Documentação Aprimorada**: Exemplos claros e explicação das variáveis de ambiente

## 🔑 Configuração

1. Copie o arquivo de exemplo de ambiente:
   ```bash
   cp .env.example .env
   ```

2. Edite o `.env` para personalizar as configurações:
   ```dotenv
   # Configuração da API
   API_TITLE=Book Dork Search API
   API_VERSION=1.0.0
   DEBUG=false

   # Configuração do Servidor
   HOST=0.0.0.0
   PORT=8000

   # Configuração de CORS (RESTRITA para segurança)
   ALLOWED_ORIGINS=http://localhost:3000,http://localhost:8080

   # Limitação de Taxa (requisições por IP por janela)
   RATE_LIMIT_REQUESTS=100
   RATE_LIMIT_WINDOW=60  # segundos

   # Configuração de Busca
   DDGS_TIMEOUT=10
   OPENLIBRARY_TIMEOUT=8
   ARCHIVE_TIMEOUT=8
   MAX_RESULTS_PER_SOURCE=10
   MAX_PREVIEW_RESULTS=5

   # Configuração de Cache
   CACHE_ENABLED=true
   CACHE_TTL=300        # 5 minutos
   CACHE_MAXSIZE=100    # Máximo de entradas no cache

   # Configuração HTTP
   USER_AGENT=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36
   REQUEST_TIMEOUT=10
   PREVIEW_TIMEOUT=5

   # Tipos de Arquivo & Análise de Conteúdo
   DEFAULT_FILETYPES=pdf,epub,mobi
   BOOK_KEYWORDS=book,livro,ebook,pdf,epub,mobi

   # Serviços Externos
   SEARXNG_URL=http://searxng:8080/search
   ```

## 🚀 Uso

### Deploy em Produção
```bash
docker compose up -d
```
Acesse a API em: `http://localhost:8000`  
Documentação interativa: `http://localhost:8000/docs`

### Modo de Desenvolvimento (com recarregamento automático)
```bash
docker compose up
```
A aplicação será recarregada automaticamente quando você modificar código no diretório `app/`.

### Instalação Manual (sem Docker)
```bash
# Instale as dependências
pip install -r requirements.txt

# Execute a aplicação
uvicorn app.main:app --reload
```

## 🛡️ Funcionalidades de Segurança

- **Limitação de Taxa**: 100 requisições por minuto por IP (configurável)
- **Validação de Entrada**: Modelos Pydantic rigorosos com sanitização para todas as entradas
- **Proteção CORS**: Apenas origens especificadas são permitidas (não `*`)
- **Segurança do Container**: Executa como usuário não-root no Docker
- **Tratamento de Erros**: Mensagens genéricas de erro para evitar vazamento de informações
- **Limites de Tamanho de Requisição**: Implicitamente controlado por timeouts e validação

## 📊 Monitoramento & Observabilidade

- **Health Check**: `GET /health` retorna o status do serviço
- **Logging Estruturado**: Todos os logs em formato JSON para fácil parsing
- **Métricas Detalhadas**: Logs incluem contagem de requisições por fonte (DDG, OpenLibrary, Archive)
- **Rastreamento de Erros**: Logging completo de exceções com stack traces

## 📖 Documentação da API

Após iniciar, visite:
- **Swagger UI**: `http://localhost:8000/docs`
- **ReDoc**: `http://localhost:8000/redoc`

### Exemplo de Requisição
```bash
curl -X POST "http://localhost:8000/search" \
  -H "Content-Type: application/json" \
  -d '{
    "title": "senhor dos anéis",
    "author": "J.R.R. Tolkien",
    "year": 1954,
    "filetypes": ["pdf", "epub"],
    "frase": "\"um anel para governá-los todos\""
  }'
```

### Entendendo o Campo "source"
Cada resultado inclui um campo `source` indicando **onde o resultado foi encontrado**, não necessariamente o domínio da URL:

- `"duckduckgo"`: Encontrado via busca no DuckDuckGo (pode apontar para qualquer site)
- `"openlibrary"`: Resultado direto da API do OpenLibrary (dados estruturados de livros)
- `"archive"`: Resultado direto da API do Internet Archive (livros/arquivos digitais)

> 💡 **Importante**: Ver `"source": "duckduckgo"` com uma URL para `archive.org` é normal e esperado - significa que o DuckDuckGo encontrou esse link do Archive durante sua busca na web.

## 🐳 Detalhes do Docker

A imagem Docker otimizada para produção inclui:
- Execução como usuário não-root (`appuser`)
- Imagem base slim (`python:3.9-slim`)
- Superfície de ataque mínima
- Montagens de volume para desenvolvimento (`./app:/app/app`)
- Suporte a arquivo de ambiente (`.env`)

## 📋 Funcionalidades

- 🔍 **Busca multi-fonte**: DuckDuckGo, OpenLibrary, Internet Archive
- 📄 **Suporte a formatos**: PDF, EPUB, MOBI, TXT, DJVU
- 🏷️ **Extração de metadados**: Autor, ano, editora, informações
- 🔗 **Links de download diretos**: Quando disponíveis na fonte
- 👁️‍🗨️ **Análise de conteúdo**: Detecção de livro/formato via palavras-chave
- 🌐 **Metabusca**: Via instância SearXNG (configurável)
- 📦 **Deduplicação**: Remoção inteligente de duplicados por URL
- 👀 **Pré-visualizações**: Extração de título/descrição para resultados web (quando apropriado)
- ☁️ **Detecção de Google Drive**: Tratamento especial para links do Drive com URLs de pré-visualização/download

## 📝 Formato da Resposta

```json
{
  "query": "seus termos de busca",
  "total": 24,
  "results": [
    {
      "title": "Título do Livro",
      "url": "https://exemplo.com/livro.pdf",
      "source": "openlibrary",
      "autor": "Nome do Autor",
      "ano": 1998,
      "is_book": true,
      "is_pdf": true,
      "is_epub": false,
      // ... campos adicionais baseados na fonte
    }
  ]
}
```

## 🤝 Contribuindo

1. Faça um fork do repositório
2. Crie uma branch para功能 (`git checkout -b feature/recurso-incrivel`)
3. Faça commit das suas alterações (`git commit -m 'Adicionar recurso incrível'`)
4. Envie para a branch (`git push origin feature/recurso-incrivel`)
5. Abra um Pull Request

## 📄 Licença

Este projeto é de código aberto e disponível sob a [Licença MIT](LICENSE).

---

**Desenvolvido com ❤️ para a comunidade de conhecimento aberto**  
*Sempre respeite as leis de direitos autorais e os termos de serviço dos sites fonte.*