# Деплой проекта на GitHub (cs16-replay-studio)

## Статус

- gh CLI установлен и **авторизован** (аккаунт `satansuka-s`, scopes: repo).
- **GitHub отказывает в создании нового репозитория** для этого аккаунта:
  `GraphQL: Trade controls restricted owner/creator can't create repositories`
  (политика GitHub для аккаунтов из санкционных регионов). Пуш в **уже
  существующий** репозиторий при этом разрешён.

## Варианты

### A. Существующий GitHub-репозиторий (быстрее всего)
Создать репозиторий может только GitHub-сервис, но у вас уже есть
`satansuka-s/arb` и `satansuka-s/Nagi` (оба публичные). Если нужно —
можно добавить проект папкой в один из них, либо (рекомендуется) получить
доступ к аккаунту без ограничений.

### B. Новый GitHub-аккаунт без ограничений
Зарегистрируйте аккаунт (email вне санкционного региона, подтверждение
личности). После этого:
```
cd C:\dev\cs16db
gh auth login --hostname github.com --git-protocol https --web
gh repo create cs16-replay-studio --private --source . --push
```
или вручную: создать репо на github.com → `deploy_to_github.bat URL`.

### C. Альтернативные хосты (рекомендую, если GitHub недоступен)
- **GitLab.com** — `gitlab.com/projects/new`, затем:
  `deploy_to_github.bat https://gitlab.com/USER/cs16-replay-studio.git`
- **Codeberg.org** — то же самое.

## Оффлайн-копия (уже готова)
Полная история (все ветки и ревизии) собрана в bundle:
```
C:\Users\Lilu\Documents\Проект по умолчанию\cs16-replay-studio.bundle  (489 МБ)
```
Восстановить на любом компьютере:
```
git clone cs16-replay-studio.bundle cs16-replay-studio
```
