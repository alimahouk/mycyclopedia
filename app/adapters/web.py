import functools
import random
import uuid
import warnings

from flask import (
    abort,
    make_response,
    redirect,
    Response,
    render_template,
    request,
    stream_with_context
)
from werkzeug.exceptions import HTTPException

from app.config import (
    search_inspiration,
    Configuration,
    ProtocolKey,
    ResponseStatus,
    UserTopicProficiency
)
from app.modules import (
    entry,
    user,
    user_session
)
from app.modules.user import User
from app.modules.user_session import UserSession


def _auth_required(func):
    """
    [DECORATOR] Makes sure a valid session exists for the user
    making the request before proceeding with the called function.
    """

    @functools.wraps(func)
    def wrapper_auth_required(*args, **kwargs):
        authenticated = False
        session_id = request.cookies.get(ProtocolKey.USER_SESSION_ID)
        if session_id and UserSession.exists(session_id):
            authenticated = True

        if authenticated:
            value = func(*args, **kwargs)
        else:
            abort(_map_response_status(ResponseStatus.UNAUTHORIZED))

        return value
    return wrapper_auth_required


def _deprecated(func):
    """
    [DECORATOR] This is a decorator which can be used to mark functions
    as deprecated. It will result in a warning being emitted
    when the function is used.
    """

    @functools.wraps(func)
    def new_func(*args, **kwargs):
        warnings.simplefilter("always", DeprecationWarning)  # Turn off filter.
        warnings.warn("Call to deprecated function {}.".format(func.__name__),
                      category=DeprecationWarning,
                      stacklevel=2)
        warnings.simplefilter("default", DeprecationWarning)  # Reset filter.

        return func(*args, **kwargs)
    return new_func


def _map_response_status(response_status: ResponseStatus) -> int:
    """
    Maps service response status codes to HTTP response status codes."""

    """Set to the HTTP Internal Server Error code by default because if
    this doesn't get set to the correct code later on then it's likely
    because of an internal server error.
    """

    ret = 500
    if response_status == ResponseStatus.OK:
        ret = 200
    elif response_status == ResponseStatus.BAD_REQUEST:
        ret = 400
    elif response_status == ResponseStatus.CREATED:
        ret = 201
    elif response_status == ResponseStatus.FORBIDDEN:
        ret = 403
    elif response_status == ResponseStatus.INTERNAL_SERVER_ERROR:
        ret = 500
    elif response_status == ResponseStatus.NO_CONTENT:
        ret = 204
    elif response_status == ResponseStatus.NOT_ALLOWED:
        ret = 405
    elif response_status == ResponseStatus.NOT_FOUND:
        ret = 404
    elif response_status == ResponseStatus.NOT_IMPLEMENTED:
        ret = 501
    elif response_status == ResponseStatus.PAYLOAD_TOO_LARGE:
        ret = 413
    elif response_status == ResponseStatus.TOO_MANY_REQUESTS:
        ret = 429
    elif response_status == ResponseStatus.UNAUTHORIZED:
        ret = 401
    return ret


def _session_id() -> str:
    session_id = request.cookies.get(ProtocolKey.USER_SESSION_ID)
    if not session_id:
        session_id = request.cookies.get(ProtocolKey.SESSION_ID)

    if not session_id:
        # Generate an ephemeral session ID to uniquely identify this visitor.
        session_id = UserSession.generate_id()
    return session_id


def _stub(func):
    """
    [DECORATOR]
    """

    @functools.wraps(func)
    def wrapper_stub():
        error = {
            ProtocolKey.ERROR: {
                ProtocolKey.ERROR_CODE: ResponseStatus.NOT_IMPLEMENTED.value,
                ProtocolKey.ERROR_MESSAGE: "This function has not been implemented yet.",
            }
        }
        response = make_response(error, _map_response_status(
            ResponseStatus.NOT_IMPLEMENTED))
        # Clients would cache this response by default - disable that behavior.
        response.headers["Cache-Control"] = "no-store"

        return response
    return wrapper_stub


def entry_page(entry_id: str) -> Response:
    session_id = _session_id()
    user_session.update_session(session_id)

    try:
        entry_id = uuid.UUID(entry_id)
    except:
        entry_id = None

    service_response = entry.get_entry(session_id, entry_id)
    if service_response[1] == ResponseStatus.OK:
        user = User.get_by_session(session_id)
        e = service_response[0]
        http_response = make_response(
            render_template("pages/entry.html", entry=e, current_user=user, debug_mode=str(Configuration.DEBUG)),
            _map_response_status(ResponseStatus.OK)
        )

    if not request.cookies.get(ProtocolKey.USER_SESSION_ID):
        if Configuration.DEBUG:
            secure_cookie = False
        else:
            secure_cookie = True
        http_response.set_cookie(
            ProtocolKey.SESSION_ID, session_id, secure=secure_cookie)

    if service_response[1] == ResponseStatus.OK:
        return http_response
    else:
        abort(_map_response_status(service_response[1]), description=service_response[0])


def error_bad_request(e: HTTPException) -> Response:
    error = e.description
    if isinstance(error, dict):
        error_code = error[ProtocolKey.ERROR][ProtocolKey.ERROR_CODE]
        error_message = error[ProtocolKey.ERROR][ProtocolKey.ERROR_MESSAGE]
    else:
        error_code = 400
        error_message = error

    http_response = make_response(
        render_template("pages/errors/400.html", error_message=error_message),
        _map_response_status(error_code)
    )
    return http_response


def error_forbidden(e: HTTPException) -> Response:
    error = e.description
    if isinstance(error, dict):
        error_code = error[ProtocolKey.ERROR][ProtocolKey.ERROR_CODE]
        error_message = error[ProtocolKey.ERROR][ProtocolKey.ERROR_MESSAGE]
    else:
        error_code = 403
        error_message = error

    http_response = make_response(
        render_template("pages/errors/403.html", error_message=error_message),
        _map_response_status(error_code)
    )
    return http_response


def error_not_allowed(e: HTTPException) -> Response:
    error = e.description
    if isinstance(error, dict):
        error_code = error[ProtocolKey.ERROR][ProtocolKey.ERROR_CODE]
        error_message = error[ProtocolKey.ERROR][ProtocolKey.ERROR_MESSAGE]
    else:
        error_code = 405
        error_message = error

    http_response = make_response(
        render_template("pages/errors/405.html", error_message=error_message),
        _map_response_status(error_code)
    )
    return http_response


def error_not_found(e: HTTPException) -> Response:
    error = e.description
    if isinstance(error, dict):
        error_code = error[ProtocolKey.ERROR][ProtocolKey.ERROR_CODE]
        error_message = error[ProtocolKey.ERROR][ProtocolKey.ERROR_MESSAGE]
    else:
        error_code = 404
        error_message = error

    http_response = make_response(
        render_template("pages/errors/404.html", error_message=error_message),
        _map_response_status(error_code)
    )
    return http_response


def error_uauthorized(e: HTTPException) -> Response:
    error = e.description
    if isinstance(error, dict):
        error_code = error[ProtocolKey.ERROR][ProtocolKey.ERROR_CODE]
        error_message = error[ProtocolKey.ERROR][ProtocolKey.ERROR_MESSAGE]
    else:
        error_code = 401
        error_message = error

    http_response = make_response(
        render_template("pages/errors/401.html", error_message=error_message),
        _map_response_status(error_code)
    )
    return http_response


def error_internal_server(e: HTTPException) -> Response:
    error = e.description
    if isinstance(error, dict):
        error_code = error[ProtocolKey.ERROR][ProtocolKey.ERROR_CODE]
        error_message = error[ProtocolKey.ERROR][ProtocolKey.ERROR_MESSAGE]
    else:
        error_code = 500
        error_message = error

    http_response = make_response(
        render_template("pages/errors/500.html", error_message=error_message),
        _map_response_status(error_code)
    )
    return http_response


def get_entry_cover_image(entry_id: str) -> Response:
    return Response(
        stream_with_context(entry.get_cover_image(uuid.UUID(entry_id))),
        content_type="text/event-stream"
    )


def get_entry_related_topics(entry_id: str) -> Response:
    return Response(
        stream_with_context(entry.get_related_topics(uuid.UUID(entry_id))),
        content_type="text/event-stream"
    )


def index() -> Response:
    session_id = _session_id()
    if session_id and UserSession.exists(session_id):
        user = User.get_by_session(session_id)

        service_response = entry.get_entries(session_id)
        entries = service_response[0]

        http_response = make_response(
            render_template("pages/index.html", current_user=user, entries=entries),
            _map_response_status(service_response[1])
        )
    else:
        examples = random.sample(search_inspiration, 5)
        http_response = make_response(
            render_template("pages/index.html", examples=examples),
            _map_response_status(ResponseStatus.OK)
        )

    if not request.cookies.get(ProtocolKey.USER_SESSION_ID):
        if Configuration.DEBUG:
            secure_cookie = False
        else:
            secure_cookie = True
        http_response.set_cookie(
            ProtocolKey.SESSION_ID, session_id, secure=secure_cookie)

    return http_response


def join() -> Response:
    session_id = _session_id()
    user_session.update_session(session_id)

    http_response = make_response(
        render_template("pages/join.html"),
        _map_response_status(ResponseStatus.OK)
    )

    if not request.cookies.get(ProtocolKey.USER_SESSION_ID):
        if Configuration.DEBUG:
            secure_cookie = False
        else:
            secure_cookie = True
        http_response.set_cookie(
            ProtocolKey.SESSION_ID, session_id, secure=secure_cookie)

    return http_response


def join_request() -> Response:
    session_id = request.cookies.get(ProtocolKey.USER_SESSION_ID)
    if session_id and UserSession.exists(session_id):
        # User is already logged in.
        return redirect("/")

    email = request.form.get(ProtocolKey.EMAIL_ADDRESS)
    password = request.form.get(ProtocolKey.PASSWORD)

    service_response = user.join(
        email_address=email,
        password=password
    )
    if ProtocolKey.USER_SESSION in service_response[0]:
        if Configuration.DEBUG:
            secure_cookie = False
        else:
            secure_cookie = True

        session = service_response[0][ProtocolKey.USER_SESSION]
        session_id = session[ProtocolKey.ID]
        http_response = redirect("/")
        http_response.set_cookie(
            ProtocolKey.USER_SESSION_ID, session_id, secure=secure_cookie)
        # Update after joining because session won't exist before it.
        user_session.update_session(session_id)

        return http_response
    else:
        error = service_response[0][ProtocolKey.ERROR][ProtocolKey.ERROR_MESSAGE]
        http_response = make_response(
            render_template("pages/join.html", error_message=error),
            _map_response_status(ResponseStatus.OK)
        )
        return http_response


def log_in() -> Response:
    session_id = _session_id()
    user_session.update_session(session_id)

    http_response = make_response(
        render_template("pages/login.html"),
        _map_response_status(ResponseStatus.OK)
    )

    if not request.cookies.get(ProtocolKey.USER_SESSION_ID):
        if Configuration.DEBUG:
            secure_cookie = False
        else:
            secure_cookie = True
        http_response.set_cookie(
            ProtocolKey.SESSION_ID, session_id, secure=secure_cookie)

    return http_response


def log_in_request() -> Response:
    session_id = request.cookies.get(ProtocolKey.USER_SESSION_ID)
    if session_id and UserSession.exists(session_id):
        # User is already logged in.
        return redirect("/")

    email = request.form.get(ProtocolKey.EMAIL_ADDRESS)
    password = request.form.get(ProtocolKey.PASSWORD)

    service_response = user.log_in(email, password)
    if ProtocolKey.USER_SESSION in service_response[0]:
        if Configuration.DEBUG:
            secure_cookie = False
        else:
            secure_cookie = True

        session = service_response[0][ProtocolKey.USER_SESSION]
        session_id = session[ProtocolKey.ID]
        http_response = redirect("/")
        http_response.set_cookie(ProtocolKey.USER_SESSION_ID, session_id, secure=secure_cookie)
        # Update after joining because session won't exist before it.
        user_session.update_session(session_id)

        return http_response
    else:
        error = service_response[0][ProtocolKey.ERROR][ProtocolKey.ERROR_MESSAGE]
        http_response = make_response(
            render_template("pages/login.html", error_message=error),
            _map_response_status(ResponseStatus.OK)
        )
        return http_response


@_auth_required
def log_out() -> Response:
    session_id = _session_id()
    user_session.update_session(session_id)

    service_response = user.log_out()
    http_response = redirect("/")
    if service_response[1] == ResponseStatus.OK:
        http_response.set_cookie(ProtocolKey.USER_SESSION_ID, "", expires=0)

    return http_response


def make_entry() -> Response:
    session_id = _session_id()
    user_session.update_session(session_id)

    proficiency = request.args.get(ProtocolKey.PROFICIENCY)
    topic = request.args.get(ProtocolKey.TOPIC)

    if proficiency:
        try:
            proficiency = UserTopicProficiency(int(proficiency))
        except:
            proficiency = UserTopicProficiency.INTERMEDIATE
    else:
        proficiency = UserTopicProficiency.INTERMEDIATE

    service_response = entry.make(
        session_id,
        proficiency=proficiency,
        user_topic=topic
    )
    if service_response[1] == ResponseStatus.CREATED:
        new_entry = service_response[0]
        http_response = redirect(f"/e/{new_entry[ProtocolKey.ID]}")
        return http_response
    else:
        abort(_map_response_status(service_response[1]), description=service_response[0])


def make_chat_completion(entry_id: str) -> Response:
    session_id = _session_id()

    context = request.args.get(ProtocolKey.CONTEXT)
    query = request.args.get(ProtocolKey.QUERY)
    reset = request.args.get(ProtocolKey.RESET)
    section_id = request.args.get(ProtocolKey.SECTION_ID)

    if reset == "0":
        reset_chat = False
    else:
        reset_chat = True

    return Response(
        stream_with_context(
            entry.make_chat_completion(
                context=context,
                entry_id=uuid.UUID(entry_id),
                reset_chat=reset_chat,
                section_id=uuid.UUID(section_id),
                session_id=session_id, user_query_md=query
            )
        ),
        content_type="text/event-stream"
    )


def make_entry_section(section_id: str) -> Response:
    return Response(
        stream_with_context(entry.make_section(uuid.UUID(section_id))),
        content_type="text/event-stream"
    )


def make_entry_sections(entry_id: str) -> Response:
    return Response(
        stream_with_context(entry.make_sections(uuid.UUID(entry_id))),
        content_type="text/event-stream"
    )


@_auth_required
def remove_entry(entry_id: str) -> Response:
    session_id = _session_id()
    user_session.update_session(session_id)

    service_response = entry.remove(session_id, uuid.UUID(entry_id))
    if service_response[1] == ResponseStatus.NO_CONTENT:
        return redirect("/")
    else:
        abort(_map_response_status(service_response[1]), description=service_response[0])
