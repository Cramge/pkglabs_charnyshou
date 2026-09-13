# Лабораторная работа №1. Цветовые модели

Автор: Чернышов Матвей  
Группа: 10б  
Курс: 2  
Вариант: 10 — CMYK ↔ LAB ↔ RGB

## Запуск

Для Windows: `ColorLab.exe`.

Из исходников, в папке `lab1`:

```powershell
python -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
.venv\Scripts\python main.py
```

## Возможности

- Ввод цвета через поля, ползунки и палитры.
- Автоматический пересчёт CMYK, LAB и RGB.
- Освещение D65, D50 и E; просмотр матриц преобразования.
- Цветоделение UCR и GCR.
- Обработка выхода за охват: Clipping и Scaling.
- Динамические градиенты ползунков.

Поля применяются по Enter, при потере фокуса или после паузы 450 мс. Допускаются точка и запятая. Ползунки поддерживают стрелки и Home/End. Штриховка на палитрах и градиентах отмечает цвета вне охвата sRGB.

## Файлы

| Файл | Содержимое |
|---|---|
| `color_models.py` | Преобразования цветов и матричные операции |
| `controller.py` | Состояние, проверка ввода и пересчёт моделей |
| `main.py` | Интерфейс |
| `test_colors.py`, `test_extended.py` | Тесты математики и контроллера |
| `test_ui.py` | Тесты интерфейса |
| `REPORT.md` | Отчёт |
| `build.py`, `ColorLab.spec` | Сборка EXE |
| `BUILD_INFO.json` | Версии зависимостей и контрольные суммы сборки |

## Тесты

```powershell
.venv\Scripts\python -B -m unittest -v test_colors test_extended test_ui
```

## Сборка

```powershell
.venv\Scripts\python -m pip install -r requirements-build.txt
.venv\Scripts\python build.py
```
