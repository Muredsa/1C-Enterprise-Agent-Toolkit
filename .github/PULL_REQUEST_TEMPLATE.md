## Что изменено / What changed

<!-- Кратко опишите изменение и его пользу. / Summarize the change and its value. -->

## Безопасность / Safety

- [ ] Основная конфигурация не изменяется без явного режима живой базы. / The main configuration is not changed without an explicit live-base mode.
- [ ] Для изменяющих операций описаны резервная копия, откат и граница очистки. / Mutating operations document backup, rollback, and cleanup boundaries.
- [ ] В изменениях нет баз, секретов, клиентских конфигураций, `.cf` или `.cfe`. / The changes contain no infobases, secrets, customer configurations, `.cf`, or `.cfe` files.

## Проверка / Validation

- [ ] `python3 -m unittest discover -s tests -v`
- [ ] Документация обновлена на русском и английском, если изменилось поведение. / Russian and English documentation was updated when behavior changed.

## Совместимость / Compatibility

<!-- Укажите проверенные версии платформы и конфигураций. / List tested platform and configuration versions. -->
