class PriceNormalizer:
    @staticmethod
    def normalize(exchange: str, symbol: str, price: float) -> float:
        """
        Здесь в будущем:
        - приведение тикеров
        - учёт контрактов
        - лотов
        - inverse / linear
        """

        return float(price)
