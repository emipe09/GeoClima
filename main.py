from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import psycopg2
from psycopg2.extras import RealDictCursor
from psycopg2 import IntegrityError
from fastapi.middleware.cors import CORSMiddleware
import json

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

def get_db_connection():
    try:
        conn = psycopg2.connect(
            host="localhost",
            database="inmet_geo",
            user="postgres",
            password="postgres"  # Lembre-se de conferir sua senha
        )
        return conn
    except Exception as e:
        print(f"Erro ao conectar: {e}")
        raise HTTPException(status_code=500, detail="Erro de conexão com Banco de Dados")

class LoginRequest(BaseModel):
    email: str
    senha: str

class UsuarioCreate(BaseModel):
    nome: str
    email: str
    senha: str

@app.post("/login")
def login(user: LoginRequest):
    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    cursor.execute("SELECT id, nome, senha_hash FROM usuarios WHERE email = %s", (user.email,))
    usuario = cursor.fetchone()
    conn.close()
    
    if not usuario:
        raise HTTPException(status_code=401, detail="Usuário não encontrado")
    if usuario['senha_hash'] != user.senha:
        raise HTTPException(status_code=401, detail="Senha incorreta")
    return {"mensagem": "Login com sucesso", "usuario": usuario['nome']}

@app.post("/criar_usuario")
def criar_usuario(user: UsuarioCreate):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            "INSERT INTO usuarios (nome, email, senha_hash) VALUES (%s, %s, %s)",
            (user.nome, user.email, user.senha)
        )
        conn.commit()
        conn.close()
        return {"mensagem": "Usuário criado com sucesso!"}
    except IntegrityError:
        conn.rollback()
        conn.close()
        raise HTTPException(status_code=400, detail="Este email já está cadastrado.")
    except Exception as e:
        conn.rollback()
        conn.close()
        raise HTTPException(status_code=500, detail=f"Erro interno: {str(e)}")

@app.get("/api/estados")
def get_estados_geojson():
    conn = get_db_connection()
    cursor = conn.cursor()
    query = """
    SELECT json_build_object(
        'type', 'FeatureCollection',
        'features', json_agg(ST_AsGeoJSON(t.*)::json)
    )
    FROM (SELECT sigla_uf, nm_uf, wkb_geometry as geometry FROM uf) as t;
    """
    cursor.execute(query)
    geojson = cursor.fetchone()[0]
    conn.close()
    return geojson

@app.get("/api/estado/{sigla}/info")
def get_estado_info(sigla: str):
    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    
    # Nova Query que cruza a base original com os setores do IBGE
    query = """
    SELECT 
        (SELECT COUNT(l.ogc_fid) FROM localidades l JOIN uf u ON l.cd_uf = u.cd_uf WHERE u.sigla_uf = %s) as total_localidades,
        (SELECT COUNT(DISTINCT l.cd_mun) FROM localidades l JOIN uf u ON l.cd_uf = u.cd_uf WHERE u.sigla_uf = %s) as total_municipios,
        (SELECT COUNT(*) FROM public.br_setores_cd2022 WHERE nm_uf = (SELECT nm_uf FROM uf WHERE sigla_uf = %s)) as total_setores_ibge,
        (SELECT ROUND(SUM(area_km2)::numeric, 2) FROM public.br_setores_cd2022 WHERE nm_uf = (SELECT nm_uf FROM uf WHERE sigla_uf = %s)) as area_total_km2
    """
    cursor.execute(query, (sigla.upper(), sigla.upper(), sigla.upper(), sigla.upper()))
    dados = cursor.fetchone()
    conn.close()
    return dados

@app.get("/api/estado/{sigla}/clima")
def get_clima_estado(sigla: str):
    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    query = """
    SELECT mes, temp_media_c, n_dias FROM dados_climaticos
    WHERE uf_sigla = %s ORDER BY mes;
    """
    cursor.execute(query, (sigla.upper(),))
    dados = cursor.fetchall()
    conn.close()
    return dados

@app.get("/api/localidades/busca")
def buscar_localidade(termo: str):
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # A Mágica do PostGIS: Spatial JOIN entre o ponto da localidade e o polígono do IBGE
    query = """
    SELECT json_build_object(
        'type', 'FeatureCollection',
        'features', json_agg(ST_AsGeoJSON(t.*)::json)
    )
    FROM (
        SELECT 
            l.nm_localid, 
            l.nm_mun, 
            l.sigla_uf,
            COALESCE(s.nm_bairro, 'Área Rural/Não informado') as nm_bairro,
            s.cd_setor,
            ROUND(s.area_km2::numeric, 2) as area_setor_km2,
            l.wkb_geometry as geometry 
        FROM (
            SELECT * FROM localidades WHERE nm_localid ILIKE %s LIMIT 5
        ) l
        LEFT JOIN public.br_setores_cd2022 s 
        ON ST_Contains(ST_SetSRID(s.geom, 4674), l.wkb_geometry)
    ) as t;
    """
    cursor.execute(query, (f"%{termo}%",))
    result = cursor.fetchone()[0]
    conn.close()
    if result is None: return {"type": "FeatureCollection", "features": []}
    return result