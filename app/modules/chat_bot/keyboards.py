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
                        "type": "open_link",
                        "link": "https://vk.com/club228359093?w=donut_payment-228359093&levelId=2855",
                        "label": "Добавить генераций",
                    },
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
