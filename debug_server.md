# Диагностика проблем на сервере

## Проверки которые нужно выполнить на сервере:

### 1. Проверить запущенные процессы:
```bash
ps aux | grep python
ps aux | grep docker
ps aux | grep emex
```

### 2. Проверить cron задачи:
```bash
crontab -l
cat /var/log/cron
tail -50 /var/log/emex-cron.log
```

### 3. Проверить Docker контейнеры:
```bash
docker ps -a
docker-compose ps
```

### 4. Остановить все процессы:
```bash
# Остановить все Docker контейнеры
docker stop $(docker ps -q)
docker-compose down

# Убить Python процессы (осторожно!)
pkill -f "python.*main.py"
```

### 5. Проверить правильность cron:
Cron должен быть:
```
50 5 * * * cd /home/dev.vazovski.art/public_html/emex_project && docker-compose run --rm emex-processor python main.py >> /var/log/emex-cron.log 2>&1
```

НЕ должен быть:
```
* * * * *  # каждую минуту
*/2 * * * *  # каждые 2 минуты
```

### 6. Временно отключить cron:
```bash
# Закомментировать cron задачу
crontab -e
# добавить # в начало строки с emex

# Или полностью удалить
crontab -r
```

### Возможные причины зацикливания:
1. **Неправильный cron** - запускается каждую минуту вместо раз в день
2. **Зависший процесс** - старый процесс не завершился и продолжает работать
3. **Docker restart policy** - контейнер автоматически перезапускается
4. **Внешний планировщик** - есть еще один cron или systemd timer 