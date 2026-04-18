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
            ]
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
