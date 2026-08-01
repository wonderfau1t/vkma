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
                        "link": "https://vk.com/lesya_ostashova.targetolog?w=donut_payment-48544404&levelId=3518",
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


image_aspect_ratio_keyboard = dumps(
    {
        "buttons": [
            [
                {
                    "action": {"type": "text", "label": "1:1"},
                    "color": "primary",
                },
                {
                    "action": {"type": "text", "label": "16:9"},
                    "color": "secondary",
                },
            ],
            [
                {
                    "action": {"type": "text", "label": "9:16"},
                    "color": "secondary",
                },
                {
                    "action": {"type": "text", "label": "4:3"},
                    "color": "secondary",
                },
            ],
            [
                {
                    "action": {"type": "text", "label": "3:4"},
                    "color": "secondary",
                },
                {
                    "action": {"type": "text", "label": "3:2"},
                    "color": "secondary",
                },
            ],
            [
                {
                    "action": {"type": "text", "label": "2:3"},
                    "color": "secondary",
                },
                {
                    "action": {"type": "text", "label": "21:9"},
                    "color": "secondary",
                },
            ],
            [
                {
                    "action": {"type": "text", "label": "4:5"},
                    "color": "secondary",
                },
                {
                    "action": {"type": "text", "label": "5:4"},
                    "color": "secondary",
                },
            ],
            [
                {
                    "action": {"type": "text", "label": "Авто"},
                    "color": "positive",
                }
            ],
            [
                {
                    "action": {"type": "text", "label": "Назад"},
                    "color": "secondary",
                }
            ],
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
