from fastapi import Depends

from query_service.database.models.dummy import DummyModel
from query_service.modules.dummy.repository import DummyRepository


class DummyService:
    """Business logic for dummy models."""

    def __init__(self, repository: DummyRepository = Depends()) -> None:
        self.repository = repository

    async def create_dummy_model(self, name: str) -> None:
        """
        Create a dummy model.

        :param name: name of a dummy.
        """
        await self.repository.create_dummy_model(name=name)

    async def get_all_dummies(self, limit: int, offset: int) -> list[DummyModel]:
        """
        Get all dummy models with limit/offset pagination.

        :param limit: limit of dummies.
        :param offset: offset of dummies.
        :return: list of dummies.
        """
        return await self.repository.get_all_dummies(limit=limit, offset=offset)
