# Monitor de stock — Láminas Mundial 2026 (GitHub Actions)

Revisa el stock cada ~1 minuto **sin necesidad de tener tu PC prendido**, usando
GitHub Actions gratis. Cuando aparece stock te llega un push al celular (ntfy) y,
opcionalmente, un correo.

## Estructura del repo

```
tu-repo/
├── check_stock.py
└── .github/
    └── workflows/
        └── monitor.yml
```

> Importante: el archivo `monitor.yml` va dentro de `.github/workflows/`.

## Pasos

1. **Crea un repositorio** en GitHub (puede ser privado).
2. Sube `check_stock.py` a la raíz, y `monitor.yml` dentro de `.github/workflows/`.
3. Instala la app **ntfy** en tu celular y suscríbete a un topic único y secreto
   (ej: `diego-laminas-2026-x7k9z`).
4. En el repo ve a **Settings → Secrets and variables → Actions → New repository secret**
   y crea:
   - `NTFY_TOPIC` = el mismo topic que pusiste en la app.
   - (opcional, para correo) `USE_EMAIL` = `true`, más `EMAIL_FROM`, `EMAIL_TO`,
     `EMAIL_APP_PASSWORD` (App Password de Gmail).
5. Ve a la pestaña **Actions**, habilita los workflows si te lo pide, y lanza
   `Monitor laminas Mundial 2026` a mano una vez (**Run workflow**) para probar.
   Revisa los logs: deberían decir "sin stock todavia" si aún no hay.

Desde ahí queda corriendo solo cada 5 minutos, y dentro de cada corrida revisa
cada 60 segundos.

## Notas

- El cron de GitHub es "best-effort": en horas de alta carga puede atrasarse unos
  minutos. Para vigilancia sin huecos, un equipo siempre encendido es más fiable.
- Mientras haya stock, te puede avisar de nuevo en corridas siguientes (cada job
  arranca limpio). Para una compra a tiempo eso juega a favor: te insiste hasta
  que compres.
- Si quieres que avise por **cualquier** producto del mundial que reaparezca,
  agrega el secret `NAME_KEYWORDS` con valor `none`.
