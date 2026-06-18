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
            [
                {
                    "action": {
                        "type": "text",
                        "label": "Стоп",
                    },
                    "color": "negative",
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
            [
                {
                    "action": {
                        "type": "text",
                        "label": "Добавить генераций",
                    },
                    "color": "secondary",
                }
            ],
            [
                {
                    "action": {
                        "type": "text",
                        "label": "Стоп",
                    },
                    "color": "negative",
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
                        "label": "Назад",
                    },
                    "color": "secondary",
                },
                # {
                #     "action": {
                #         "type": "text",
                #         "label": "Стоп",
                #     },
                #     "color": "negative",
                # }
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
                        "label": "Назад",
                    },
                    "color": "primary",
                },
                # {
                #     "action": {
                #         "type": "text",
                #         "label": "Стоп",
                #     },
                #     "color": "negative",
                # }
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
                        "label": "Назад",
                    },
                    "color": "primary",
                },
                # {
                #     "action": {
                #         "type": "text",
                #         "label": "Стоп",
                #     },
                #     "color": "negative",
                # }
            ]
        ]
    }
)

empty_keyboard = dumps({"buttons": []})
