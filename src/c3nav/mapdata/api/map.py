import json
from typing import Annotated, Union

from django.core.serializers.json import DjangoJSONEncoder
from django.shortcuts import redirect
from django.utils import timezone
from ninja import Query
from ninja import Router as APIRouter
from pydantic import Field as APIField
from pydantic import PositiveInt

from c3nav import settings
from c3nav.api.auth import auth_permission_responses, auth_responses, validate_responses
from c3nav.api.exceptions import API404, APIPermissionDenied, APIRequestValidationFailed
from c3nav.api.schema import BaseSchema
from c3nav.api.utils import NonEmptyStr
from c3nav.mapdata.api.base import api_etag, api_stats, can_access_geometry
from c3nav.mapdata.models import Source
from c3nav.mapdata.models.locations import DynamicLocation, LocationRedirect, Position
from c3nav.mapdata.schemas.filters import BySearchableFilter, RemoveGeometryFilter
from c3nav.mapdata.schemas.model_base import AnyLocationID, AnyPositionID, CustomLocationID
from c3nav.mapdata.schemas.models import (AnyPositionStatusSchema, FullListableLocationSchema, FullLocationSchema,
                                          LocationDisplay, ProjectionPipelineSchema, ProjectionSchema,
                                          SlimListableLocationSchema, SlimLocationSchema, all_location_definitions,
                                          listable_location_definitions)
from c3nav.mapdata.schemas.responses import LocationGeometry, WithBoundsSchema
from c3nav.mapdata.utils.locations import (get_location_by_id_for_request, get_location_by_slug_for_request,
                                           searchable_locations_for_request, visible_locations_for_request)
from c3nav.mapdata.utils.user import can_access_editor

map_api_router = APIRouter(tags=["map"])


@map_api_router.get('/bounds/', summary="get boundaries",
                    description="get maximum boundaries of everything on the map",
                    response={200: WithBoundsSchema, **auth_responses})
@api_etag(permissions=False)
def bounds(request):
    return {
        "bounds": Source.max_bounds(),
    }


class LocationEndpointParameters(BaseSchema):
    searchable: bool = APIField(
        False,
        title='only list searchable locations',
        description='if set, only searchable locations will be listed'
    )


class LocationListFilters(BySearchableFilter, RemoveGeometryFilter):
    pass


def _location_list(request, detailed: bool, filters: LocationListFilters):
    if filters.searchable:
        locations = searchable_locations_for_request(request)
    else:
        locations = visible_locations_for_request(request).values()

    result = [obj.serialize(detailed=detailed, search=filters.searchable,
                            geometry=filters.geometry and can_access_geometry(request, obj),
                            simple_geometry=True)
              for obj in locations]
    return result


@map_api_router.get('/locations/', summary="list locations (slim)",
                    description=("Get locations (with most important attributes set)\n\n"
                                 "Possible location types:\n"+listable_location_definitions),
                    response={200: list[SlimListableLocationSchema], **validate_responses, **auth_responses})
@api_etag(base_mapdata=True)
def location_list(request, filters: Query[LocationListFilters]):
    return _location_list(request, detailed=False, filters=filters)


@map_api_router.get('/locations/full/', summary="list locations (full)",
                    description=("Get locations (with all attributes set)\n\n"
                                 "Possible location types:\n"+listable_location_definitions),
                    response={200: list[FullListableLocationSchema], **validate_responses, **auth_responses})
@api_etag(base_mapdata=True)
def location_list_full(request, filters: Query[LocationListFilters]):
    return _location_list(request, detailed=True, filters=filters)


def _location_retrieve(request, location, detailed: bool, geometry: bool, show_redirects: bool):
    if location is None:
        raise API404()

    if isinstance(location, LocationRedirect):
        if not show_redirects:
            return redirect('../' + str(location.target.slug))  # todo: use reverse, make pk and slug both work

    if isinstance(location, (DynamicLocation, Position)):
        request._target_etag = None
        request._target_cache_key = None

    return location.serialize(
        detailed=detailed,
        geometry=geometry and can_access_geometry(request, location),
        simple_geometry=True
    )


def _location_display(request, location):
    if location is None:
        raise API404()

    if isinstance(location, LocationRedirect):
        return redirect('../' + str(location.target.slug) + '/details/')  # todo: use reverse, make pk+slug work

    result = location.details_display(
        detailed_geometry=can_access_geometry(request, location),
        editor_url=can_access_editor(request)
    )
    return json.loads(json.dumps(result, cls=DjangoJSONEncoder))  # todo: wtf?? well we need to get rid of lazy strings


def _location_geometry(request, location):
    # todo: cache, visibility, etc…

    if location is None:
        raise API404()

    if isinstance(location, LocationRedirect):
        return redirect('../' + str(location.target.slug) + '/geometry/')  # todo: use reverse, make pk+slug work

    return LocationGeometry(
        id=location.pk,
        level=getattr(location, 'level_id', None),
        geometry=location.get_geometry(
            detailed_geometry=can_access_geometry(request, location)
        )
    )


class ShowRedirects(BaseSchema):
    show_redirects: bool = APIField(
        False,
        name="show redirects",
        description="whether to show redirects instead of sending a redirect response",
    )


@map_api_router.get('/locations/{location_id}/', summary="location by ID (slim)",
                    description=("Get locations by ID (with all attributes set)\n\n"
                                 "Possible location types:\n"+all_location_definitions),
                    response={200: SlimLocationSchema, **API404.dict(), **validate_responses, **auth_responses})
@api_stats('location_get')
@api_etag(base_mapdata=True)
def location_by_id(request, location_id: AnyLocationID, filters: Query[RemoveGeometryFilter],
                   redirects: Query[ShowRedirects]):
    return _location_retrieve(
        request,
        get_location_by_id_for_request(location_id, request),
        detailed=False, geometry=filters.geometry, show_redirects=redirects.show_redirects,
    )


@map_api_router.get('/locations/{location_id}/full/', summary="location by ID (full)",
                    description=("Get location by ID (with all attributes set)\n\n"
                                 "Possible location types:\n"+all_location_definitions),
                    response={200: FullLocationSchema, **API404.dict(), **validate_responses, **auth_responses})
@api_stats('location_get')
@api_etag(base_mapdata=True)
def location_by_id_full(request, location_id: AnyLocationID, filters: Query[RemoveGeometryFilter],
                        redirects: Query[ShowRedirects]):
    return _location_retrieve(
        request,
        get_location_by_id_for_request(location_id, request),
        detailed=True, geometry=filters.geometry, show_redirects=redirects.show_redirects,
    )


@map_api_router.get('/locations/{location_id}/display/', summary="location display by ID",
                    description="Get location display information by ID",
                    response={200: LocationDisplay, **API404.dict(), **auth_responses})
@api_stats('location_display')
@api_etag(base_mapdata=True)
def location_by_id_display(request, location_id: AnyLocationID):
    return _location_display(
        request,
        get_location_by_id_for_request(location_id, request),
    )


@map_api_router.get('/locations/{location_id}/geometry/', summary="location geometry by id",
                    description="Get location geometry (if available) by ID",
                    response={200: LocationGeometry, **API404.dict(), **auth_responses})
@api_stats('location_geometry')
@api_etag(base_mapdata=True)
def location_by_id_geometry(request, location_id: AnyLocationID):
    return _location_geometry(
        request,
        get_location_by_id_for_request(location_id, request),
    )


@map_api_router.get('/locations/by-slug/{location_slug}/', summary="location by slug (slim)",
                    description=("Get location by slug (with most important attributes set)\n\n"
                                 "Possible location types:\n"+all_location_definitions),
                    response={200: SlimLocationSchema, **API404.dict(), **validate_responses, **auth_responses})
@api_stats('location_get')
@api_etag(base_mapdata=True)
def location_by_slug(request, location_slug: NonEmptyStr, filters: Query[RemoveGeometryFilter],
                     redirects: Query[ShowRedirects]):
    return _location_retrieve(
        request,
        get_location_by_slug_for_request(location_slug, request),
        detailed=False, geometry=filters.geometry, show_redirects=redirects.show_redirects,
    )


@map_api_router.get('/locations/by-slug/{location_slug}/full/', summary="location by slug (full)",
                    description=("Get location by slug (with all attributes set)\n\n"
                                 "Possible location types:\n"+all_location_definitions),
                    response={200: FullLocationSchema, **API404.dict(), **validate_responses, **auth_responses})
@api_stats('location_get')
@api_etag(base_mapdata=True)
def location_by_slug_full(request, location_slug: NonEmptyStr, filters: Query[RemoveGeometryFilter],
                          redirects: Query[ShowRedirects]):
    return _location_retrieve(
        request,
        get_location_by_slug_for_request(location_slug, request),
        detailed=True, geometry=filters.geometry, show_redirects=redirects.show_redirects,
    )


@map_api_router.get('/locations/by-slug/{location_slug}/display/', summary="location display by slug",
                    description="Get location display information by slug",
                    response={200: LocationDisplay, **API404.dict(), **auth_responses})
@api_stats('location_display')
@api_etag(base_mapdata=True)
def location_by_slug_display(request, location_slug: NonEmptyStr):
    return _location_display(
        request,
        get_location_by_slug_for_request(location_slug, request),
    )


@map_api_router.get('/locations/by-slug/{location_slug}/geometry/', summary="location geometry by slug",
                    description="Get location geometry (if available) by slug",
                    response={200: LocationGeometry, **API404.dict(), **auth_responses})
@api_stats('location_geometry')
@api_etag(base_mapdata=True)
def location_by_slug_geometry(request, location_slug: NonEmptyStr):
    return _location_geometry(
        request,
        get_location_by_slug_for_request(location_slug, request),
    )


@map_api_router.get('/positions/{position_id}/', summary="moving position coordinates",
                    description="get current coordinates of a moving position / dynamic location",
                    response={200: AnyPositionStatusSchema, **API404.dict(), **auth_responses})
@api_stats('get_position')
def get_position_by_id(request, position_id: AnyPositionID):
    # no caching for obvious reasons!
    location = None
    if isinstance(position_id, int) or position_id.isdigit():
        location = get_location_by_id_for_request(position_id, request)
        if not isinstance(location, DynamicLocation):
            raise API404()
    if location is None and position_id.startswith('p:'):
        try:
            location = Position.objects.get(secret=position_id[2:])
        except Position.DoesNotExist:
            raise API404()
    return location.serialize_position()


class UpdatePositionSchema(BaseSchema):
    coordinates_id: Union[
        Annotated[CustomLocationID, APIField(title="set coordinates")],
        Annotated[None, APIField(title="unset coordinates")],
    ] = APIField(
        description="coordinates to set the location to or null to unset it"
    )
    timeout: Union[
        Annotated[PositiveInt, APIField(title="new timeout")],
        Annotated[None, APIField(title="don't change")],
    ] = APIField(
        None,
        title="timeout",
        description="timeout for this new location in seconds, or None if not to change it",
    )


@map_api_router.put('/positions/{position_id}/', url_name="position-update",
                    summary="set moving position",
                    description="only the string ID for the position secret must be used",
                    response={200: AnyPositionStatusSchema, **API404.dict(), **auth_permission_responses})
def set_position(request, position_id: AnyPositionID, update: UpdatePositionSchema):
    # todo: may an API key do this?
    if not isinstance(position_id, str) or not position_id.startswith('p:'):
        raise API404()
    try:
        location = Position.objects.get(secret=position_id[2:])
    except Position.DoesNotExist:
        raise API404()
    if location.owner != request.user:
        raise APIPermissionDenied()

    coordinates = get_location_by_id_for_request(update.coordinates_id, request)
    if coordinates is None:
        raise APIRequestValidationFailed('Cant resolve coordinates.')

    location.coordinates_id = update.coordinates_id
    location.timeout = update.timeout
    location.last_coordinates_update = timezone.now()
    location.save()

    return location.serialize_position()


@map_api_router.get('/projection/', summary='get proj4 string',
                    description="get proj4 string for converting WGS84 coordinates to c3nva coordinates",
                    response={200: Union[ProjectionSchema, ProjectionPipelineSchema], **auth_responses})
def get_projection(request):
    obj = {
        "pipeline": settings.PROJECTION_TRANSFORMER_STRING
    }
    if True:
        obj.update({
            'proj4': settings.PROJECTION_PROJ4,
            'zero_point': settings.PROJECTION_ZERO_POINT,
            'rotation': settings.PROJECTION_ROTATION,
            'rotation_matrix': settings.PROJECTION_ROTATION_MATRIX,
        })
    return obj
