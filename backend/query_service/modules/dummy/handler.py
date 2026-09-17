from fastapi import APIRouter
from fastapi.param_functions import Depends

from query_service.database.models.dummy import DummyModel
from query_service.modules.dummy.schema import (
    DummyModelDTO,
    DummyModelRequestDTO,
)
from query_service.modules.dummy.service import DummyService

router = APIRouter()


@router.get("/", response_model=list[DummyModelDTO])
async def get_dummy_models(
    limit: int = 10,
    offset: int = 0,
    dummy_service: DummyService = Depends(),
) -> list[DummyModel]:
    """
    Retrieve all dummy objects from the database.

    :param limit: limit of dummy objects, defaults to 10.
    :param offset: offset of dummy objects, defaults to 0.
    :param dummy_service: service for dummy models.
    :return: list of dummy objects from database.
    """
    return await dummy_service.get_all_dummies(limit=limit, offset=offset)


@router.put("/")
async def create_dummy_model(
    new_dummy_object: DummyModelRequestDTO,
    dummy_service: DummyService = Depends(),
) -> None:
    """
    Creates dummy model in the database.

    :param new_dummy_object: new dummy model item.
    :param dummy_service: service for dummy models.
    """
    await dummy_service.create_dummy_model(name=new_dummy_object.name)
