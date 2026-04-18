def get_declension(number, singular, plural_genitive, plural):
    """
    Определяет правильное склонение для чисел.
    :param number: Число
    :param singular: Единственное число (например, "день")
    :param plural_genitive: Родительный падеж множественного числа (например, "дня")
    :param plural: Множественное число (например, "дней")
    :return: Правильное склонение
    """
    number = abs(number) % 100
    if 11 <= number <= 19:
        return plural
    number %= 10
    if number == 1:
        return singular
    if 2 <= number <= 4:
        return plural_genitive
    return plural


def format_time(days, hours, minutes):
    days_word = get_declension(days, "день", "дня", "дней")
    hours_word = get_declension(hours, "час", "часа", "часов")
    minutes_word = get_declension(minutes, "минута", "минуты", "минут")

    return f"Среднее время между публикациями составляет: {days} {days_word}, {hours} {hours_word}, {minutes} {minutes_word}.\n"
