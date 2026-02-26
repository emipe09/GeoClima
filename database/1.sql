CREATE TABLE public.usuarios (
    id SERIAL PRIMARY KEY,
    nome VARCHAR(100) NOT NULL,
    email VARCHAR(150) UNIQUE NOT NULL,
    senha_hash VARCHAR(255) NOT NULL, -- Armazene apenas o hash da senha, nunca o texto puro
    data_cadastro TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE public.dados_climaticos (
    id SERIAL PRIMARY KEY,
    uf_sigla VARCHAR(2) NOT NULL, -- Corresponde à coluna 'UF' do CSV e 'sigla_uf' da tabela UF
    ano INT NOT NULL,
    mes INT NOT NULL,
    temp_media_c NUMERIC(5, 2), -- Corresponde à coluna 'temp_media_c'
    n_dias INT,                 -- Corresponde à coluna 'n_dias'
    CONSTRAINT uq_clima_uf_periodo UNIQUE (uf_sigla, ano, mes) -- Evita duplicidade de dados para o mesmo mês/UF
);

-- Garante que não há UFs repetidas e cria um índice para busca rápida
ALTER TABLE public.uf ADD CONSTRAINT uq_uf_sigla UNIQUE (sigla_uf);

-- Cria a chave estrangeira ligando os dados climáticos ao mapa
ALTER TABLE public.dados_climaticos
ADD CONSTRAINT fk_clima_uf
FOREIGN KEY (uf_sigla) REFERENCES public.uf (sigla_uf);

-- Índice para contar localidades por estado rapidamente
CREATE INDEX idx_localidades_cd_uf ON public.localidades (cd_uf);

-- Índice para a busca textual de localidades por nome
CREATE INDEX idx_localidades_nome ON public.localidades (nm_localid);


