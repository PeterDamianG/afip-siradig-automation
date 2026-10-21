# opencode-skill-creator (adaptación para OpenCode)

Instalado globalmente, no copiado en el proyecto.

- Plugin npm: `opencode-skill-creator` (v0.3.6, Apache-2.0).
- Configuración global: `~/.config/opencode/opencode.json` → `plugins: ["opencode-skill-creator"]`.
- Skill instalado: `~/.config/opencode/skills/opencode-skill-creator/`.
- Origen: https://github.com/antongulin/opencode-skill-creator
- Basado en: https://github.com/anthropics/skills/tree/main/skills/skill-creator

## Uso

En cualquier proyecto de OpenCode:

```
Use opencode-skill-creator to create a skill that ...
Use opencode-skill-creator to improve the description of my skill at .opencode/skills/...
```

Herramientas que expone: `skill_validate`, `skill_parse`, `skill_eval`,
`skill_improve_description`, `skill_optimize_loop`, `skill_aggregate_benchmark`,
`skill_generate_report`, `skill_serve_review`, `skill_stop_review`,
`skill_export_static_review`, y el manejo de descripciones gold-standard.

## Notas

- Para evaluar un skill instalado, moverlo fuera de `.opencode/skills/` durante la prueba
  (el plugin crea un skill sintético con el mismo nombre base).
- El detalle del flujo del proyecto está en el skill `pagosafip-skill-maintenance`.
