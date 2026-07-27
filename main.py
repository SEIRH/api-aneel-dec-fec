# ==============================================================================
# API Intermediária ANEEL — Indicadores de Continuidade (Filtrado EPB/EBO + Indicadores)
# ------------------------------------------------------------------------------
# Hospedagem recomendada : Render.com (free tier)
# Consumo no Power BI    : Web.Contents no Power Query (retorna CSV)
# Cache                  : Em disco, expira a cada 24 horas
# ==============================================================================

from fastapi import FastAPI, Response
from fastapi.responses import FileResponse
import pandas as pd
import requests
import zipfile
import urllib3
import os
import tempfile
from datetime import datetime, timedelta
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

urllib3.disable_warnings()

app = FastAPI(
    title="API ANEEL - Indicadores (PB)",
    description="Filtra Indicadores de Continuidade da ANEEL para a EPB e EBO (DEC, FEC, NumCon).",
    version="1.3.0",
)

# ------------------------------------------------------------------------------
# Configurações
# ------------------------------------------------------------------------------
URL_ANEEL = "https://dadosabertos.aneel.gov.br/dataset/d5f0712e-62f6-4736-8dff-9991f10758a7/resource/4493985c-baea-429c-9df5-3030422c71d7/download/indicadores-continuidade-coletivos-2020-2029.zip"
# Regex para buscar qualquer linha que contenha EPB ou EBO
AGENTES_REGEX = "EPB|EBO" 
INDICADORES_ALVO = ["DEC", "FEC", "NumCon"]
CACHE_DURACAO_HORAS = 24
ARQUIVO_CACHE = "indicadores_pb.csv"

# ------------------------------------------------------------------------------
# Controle de Cache
# ------------------------------------------------------------------------------
_cache: dict = {
    "expira_em": None,
    "ultima_atualizacao": None,
    "erros": [],
}

def _cache_valido() -> bool:
    return (
        _cache["expira_em"] is not None
        and datetime.now() < _cache["expira_em"]
        and os.path.exists(ARQUIVO_CACHE)
    )

def _coletar_dados_aneel() -> None:
    erros = []
    
    session = requests.Session()
    retry = Retry(connect=5, read=5, backoff_factor=1)
    adapter = HTTPAdapter(max_retries=retry)
    session.mount('http://', adapter)
    session.mount('https://', adapter)

    try:
        with tempfile.TemporaryDirectory() as tmpdirname:
            zip_path = os.path.join(tmpdirname, "dados.zip")
            
            # 1. Baixa o ZIP para o disco temporário
            response = session.get(URL_ANEEL, verify=False, stream=True, timeout=60)
            response.raise_for_status()
            
            with open(zip_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=1024 * 1024):
                    if chunk:
                        f.write(chunk)
                        
            # 2. Lê direto do ZIP e aplica os múltiplos filtros em blocos
            df_pb_list = []
            with zipfile.ZipFile(zip_path, 'r') as z:
                nome_arquivo = z.namelist()[0]
                
                with z.open(nome_arquivo) as f_csv:
                    chunk_iter = pd.read_csv(f_csv, sep=';', encoding='latin1', low_memory=False, chunksize=50000)
                    
                    for chunk in chunk_iter:
                        # Filtra se a coluna CONTÉM EPB ou EBO (ignorando maiúsculas/minúsculas)
                        filtro_agente = chunk['SigAgente'].astype(str).str.contains(AGENTES_REGEX, case=False, na=False)
                        
                        # Filtra os indicadores específicos
                        filtro_indicador = chunk['SigIndicador'].isin(INDICADORES_ALVO)
                        
                        # Aplica as duas condições simultaneamente
                        pb_chunk = chunk[filtro_agente & filtro_indicador]
                        df_pb_list.append(pb_chunk)
                        
            # 3. Consolida e salva no disco do servidor
            if df_pb_list:
                df_final = pd.concat(df_pb_list, ignore_index=True)
                df_final.to_csv(ARQUIVO_CACHE, index=False, encoding="utf-8", sep=";")

    except Exception as e:
        erros.append(str(e))

    # Atualiza o status do cache
    if os.path.exists(ARQUIVO_CACHE):
        _cache["expira_em"] = datetime.now() + timedelta(hours=CACHE_DURACAO_HORAS)
        _cache["ultima_atualizacao"] = datetime.now().isoformat()
    _cache["erros"] = erros


# ------------------------------------------------------------------------------
# Endpoints da API
# ------------------------------------------------------------------------------

@app.get("/", summary="Página Inicial")
def raiz():
    return {
        "status": "API ANEEL (Indicadores PB) rodando!", 
        "instrucao": "Use o endpoint /dados no Power BI para obter o CSV filtrado."
    }

@app.get(
    "/dados",
    response_class=FileResponse,
    summary="Retorna o arquivo CSV filtrado",
    description="Use este endpoint no Power BI via Web.Contents.",
)
def get_dados():
    if not _cache_valido():
        _coletar_dados_aneel()

    if not os.path.exists(ARQUIVO_CACHE):
        return Response(
            content="Nenhum dado disponível. A conexão com a ANEEL pode ter falhado.",
            status_code=503,
            media_type="text/plain",
        )

    return FileResponse(
        path=ARQUIVO_CACHE,
        media_type="text/csv",
        filename="indicadores_pb_filtrado.csv"
    )

@app.get("/status", summary="Status do cache e da última coleta")
def get_status():
    return {
        "cache_valido": _cache_valido(),
        "ultima_atualizacao": _cache["ultima_atualizacao"],
        "expira_em": _cache["expira_em"].isoformat() if _cache["expira_em"] else None,
        "tamanho_arquivo_mb": round(os.path.getsize(ARQUIVO_CACHE) / (1024 * 1024), 2) if os.path.exists(ARQUIVO_CACHE) else 0,
        "erros_na_ultima_coleta": _cache["erros"],
    }
