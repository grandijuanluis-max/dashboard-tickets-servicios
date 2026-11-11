-- ==============================================================================
-- Integración con tu tabla existente de consultores: config_consultores
-- ==============================================================================
ALTER TABLE public.config_consultores 
ADD COLUMN IF NOT EXISTS telegram_id BIGINT;

-- ==============================================================================
-- Tabla: compromisos_diarios (Tareas / Horizonte del día)
-- ==============================================================================
CREATE TABLE IF NOT EXISTS public.compromisos_diarios (
    id BIGSERIAL PRIMARY KEY,
    consultor TEXT NOT NULL,
    tarea TEXT NOT NULL,
    fecha_objetivo DATE NOT NULL DEFAULT CURRENT_DATE,
    estado TEXT NOT NULL DEFAULT 'pendiente', -- 'pendiente' o 'completada'
    origen TEXT DEFAULT 'telegram',
    cliente TEXT DEFAULT 'GENERAL',
    modulo TEXT DEFAULT 'OTROS',
    tiempo_estimado_min INTEGER DEFAULT 60,
    id_ticket BIGINT,
    completado_por TEXT,
    completado_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Por si la tabla ya existía sin las columnas nuevas:
ALTER TABLE public.compromisos_diarios ADD COLUMN IF NOT EXISTS cliente TEXT DEFAULT 'GENERAL';
ALTER TABLE public.compromisos_diarios ADD COLUMN IF NOT EXISTS modulo TEXT DEFAULT 'OTROS';
ALTER TABLE public.compromisos_diarios ADD COLUMN IF NOT EXISTS tiempo_estimado_min INTEGER DEFAULT 60;
ALTER TABLE public.compromisos_diarios ADD COLUMN IF NOT EXISTS id_ticket BIGINT;
ALTER TABLE public.compromisos_diarios ADD COLUMN IF NOT EXISTS completado_por TEXT;
ALTER TABLE public.compromisos_diarios ADD COLUMN IF NOT EXISTS completado_at TIMESTAMP WITH TIME ZONE;

ALTER TABLE public.compromisos_diarios ENABLE ROW LEVEL SECURITY;
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_policies WHERE tablename = 'compromisos_diarios' AND policyname = 'Permitir todo en compromisos_diarios'
    ) THEN
        CREATE POLICY "Permitir todo en compromisos_diarios"
        ON public.compromisos_diarios FOR ALL USING (true) WITH CHECK (true);
    END IF;
END $$;

-- ==============================================================================
-- Nueva tabla: registro_pedidos_bot (Historial completo de audios y mensajes)
-- ==============================================================================
-- Registra todo lo pedido al asistente (por audio o texto), la intención detectada,
-- la tarea asociada y el número de ticket generado al completarse.
CREATE TABLE IF NOT EXISTS public.registro_pedidos_bot (
    id BIGSERIAL PRIMARY KEY,
    fecha_hora TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    telegram_user_id BIGINT,
    telegram_chat_id BIGINT,
    consultor TEXT,
    destinatario TEXT,
    tipo_entrada TEXT NOT NULL DEFAULT 'texto', -- 'texto' o 'audio'
    mensaje_original TEXT NOT NULL,
    intencion TEXT,
    cliente TEXT,
    modulo TEXT,
    estado TEXT NOT NULL DEFAULT 'registrado', -- 'registrado', 'pendiente', 'completada', 'error'
    id_compromiso BIGINT,
    id_ticket BIGINT,
    detalle_resultado TEXT,
    completado_at TIMESTAMP WITH TIME ZONE
);

ALTER TABLE public.registro_pedidos_bot ENABLE ROW LEVEL SECURITY;
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_policies WHERE tablename = 'registro_pedidos_bot' AND policyname = 'Permitir todo en registro_pedidos_bot'
    ) THEN
        CREATE POLICY "Permitir todo en registro_pedidos_bot"
        ON public.registro_pedidos_bot FOR ALL USING (true) WITH CHECK (true);
    END IF;
END $$;
