# poe2lab

Анализ билдов Path of Exile 2 поверх Path of Building (PoB-PoE2, headless): что сломано, какие статы и моды
стоят больше всего, что убивает на картах, что докрафтить в каждый слот, какие руны вставить и сколько это стоит.

## Установка

Нужны Windows, Python 3.12+ и git.

```
git clone --recurse-submodules https://github.com/JavelinSx/poe2lab.git
cd poe2lab
pip install -e .[dev]
```

PoB лежит git-подмодулем в `pob2/`. Если клонировали без `--recurse-submodules`, ничего страшного: при первом
запуске он подтянется сам (`git submodule update --init`).

## Использование

1. В PoB-PoE2: Import/Export Build → импорт персонажа → Generate → Copy. Сохранить код в `builds/<имя>.txt`.
2. Посмотреть группы скиллов и выбрать основной: `python -m poe2lab inspect builds/<имя>.txt`
3. Запускать анализы с `--group N` (номер группы основного скилла):

| Команда | Что делает |
|---|---|
| `report` | главное: дыры, условия, ядро урона, куда вкладываться, путь апгрейда |
| `threats` | какие удары переживаешь, как быстро лечишься |
| `slots` | вклад каждого аффикса, что докрафтить по слотам, руны с ценами |
| `compare` | точное сравнение предмета с надетым (`--item`, `--breakeven`) |
| `nodes`, `gradients` | вклад нод дерева, ценность статов |
| `dossier` | всё одним JSON (`--out`) |

Например: `python -m poe2lab report builds/titan.txt --group 4`

В Claude Code в этой папке можно просто спросить («разбери мой билд») — навык `.claude/skills/poe2-build`
знает команды и типичные ловушки.

Тесты: `python -m pytest -q`. План — `PLAN.md`, открытые вопросы — `QUESTIONS.md`.
