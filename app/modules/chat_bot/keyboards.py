from json import dumps

inline_main_menu_keyboard = dumps(
    {
        "inline": True,
        "buttons": [
            [
                {
                    "action": {
                        "type": "text",
                        "label": "Аудит сообщества",
                    },
                    "color": "primary",
                }
            ],
            [
                {
                    "action": {
                        "type": "text",
                        "label": "Генерация поста",
                    },
                    "color": "secondary",
                },
                {
                    "action": {
                        "type": "text",
                        "label": "Генерация изображения",
                    },
                    "color": "secondary",
                },
            ],
            [
                {
                    "action": {
                        "type": "text",
                        "label": "Баланс",
                    },
                    "color": "secondary",
                }
            ],
        ],
    }
)


main_menu_keyboard = dumps(
    {
        "buttons": [
            [
                {
                    "action": {
                        "type": "text",
                        "label": "Аудит сообщества",
                    },
                    "color": "primary",
                }
            ],
            [
                {
                    "action": {
                        "type": "text",
                        "label": "Генерация поста",
                    },
                    "color": "secondary",
                },
                {
                    "action": {
                        "type": "text",
                        "label": "Генерация изображения",
                    },
                    "color": "secondary",
                },
            ],
            [
                {
                    "action": {
                        "type": "text",
                        "label": "Баланс",
                    },
                    "color": "secondary",
                }
            ],
        ]
    }
)


generation_cancel_keyboard = dumps(
    {
        "buttons": [
            [
                {
                    "action": {
                        "type": "text",
                        "label": "Отмена",
                    },
                    "color": "negative",
                }
            ]
        ]
    }
)


inline_group_analysis_keyboard = dumps(
    {
        "inline": True,
        "buttons": [
            [
                {
                    "action": {
                        "type": "text",
                        "label": "Выйти из аудита",
                    },
                    "color": "primary",
                }
            ]
        ],
    }
)

to_main_menu_keyboard = dumps(
    {
        "buttons": [
            [
                {
                    "action": {
                        "type": "text",
                        "label": "Выйти из аудита",
                    },
                    "color": "primary",
                }
            ]
        ]
    }
)

empty_keyboard = dumps({"buttons": []})
