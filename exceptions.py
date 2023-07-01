class UserExcTeleramError(Exception):
    """Ошибка при отправке сообщения в Telegram."""

    pass


class UserExcRequestError(Exception):
    """Ошибка при выполнении запроса."""

    pass


class UserExcHTTPError(Exception):
    """Ошибка HTTP."""

    pass


class UserExcJSONError(Exception):
    """Ошибка при преобразовании в JSON."""

    pass
