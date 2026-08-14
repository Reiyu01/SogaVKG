from abc import ABC, abstractmethod


class AssetRepository(ABC):

    @abstractmethod
    def get_all(self):
        raise NotImplementedError

    @abstractmethod
    def get_by_code(self, asset_code: str):
        raise NotImplementedError

    @abstractmethod
    def search(self, keyword: str):
        raise NotImplementedError