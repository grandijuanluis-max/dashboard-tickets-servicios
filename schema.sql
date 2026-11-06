-- ==============================================================================
-- Integración con tu tabla existente de consultores: config_consultores
-- ==============================================================================
-- Para que el bot recuerde qué usuario de Telegram sos vos y cuál es tu jefe,
-- solo hace falta agregar la columna opcional 'telegram_id' en config_consultores:

ALTER TABLE public.config_consultores 
ADD COLUMN IF NOT EXISTS telegram_id BIGINT;

-- ==============================================================================
-- Nueva tabla: compromisos_diarios (Tareas / Horizonte del día)
-- ==============================================================================
-- Para registrar compromisos que hay que sacar sí o sí sin horario fijo
CREATE TABLE IF NOT EXISTS public.compromisos_diarios (
    id BIGSERIAL PRIMARY KEY,
    consultor TEXT NOT NULL,
    tarea TEXT NOT NULL,
    fecha_objetivo DATE NOT NULL DEFAULT CURRENT_DATE,
    estado TEXT NOT NULL DEFAULT 'pendiente', -- 'pendiente' o 'completada'
    origen TEXT DEFAULT 'telegram',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Permisos para service role
ALTER TABLE public.compromisos_diarios ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Permitir todo a service_role en compromisos" 
ON public.compromisos_diarios FOR ALL USING (true);
