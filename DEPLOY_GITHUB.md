# Деплой проекта на GitHub (cs16-replay-studio)

## Статус: ✅ опубликовано

- Репозиторий: **https://github.com/satansuka-s/cs16-replay-studio** (публичный)
- Ветка: `master`; история сжата (filter-repo убрал большие тестовые артефакты
  из истории: ~740 МБ → ~38 МБ); `origin` настроен.
- GitHub blocked *приватные* репозитории для аккаунта (trade controls),
  **публичные — создаются нормально**.

## Дальнейшие обновления

```
cd C:\dev\cs16db
git add -A && git commit -m "..."
git push
```

## Оффлайн-копия
Актуальный bundle (вся история) лежит в
`C:\Users\Lilu\Documents\Проект по умолчанию\cs16-replay-studio.bundle` (~38 МБ).
Восстановление на другом компьютере:
```
git clone cs16-replay-studio.bundle cs16-replay-studio
git remote add origin https://github.com/satansuka-s/cs16-replay-studio.git
```

## Важно (чтобы история не раздувалась снова)
В `.gitignore` добавлены и НЕЛЬЗЯ трекать: `*.dem`, `*.blend`, `*.blend1`,
`*.tar.xz`, `*.whl` — это генерируемые артефакты (демки, сцены, архивы).
Если что-то подобное нужно хранить — используйте Releases/частные бакеты.
