from starlette.applications import Starlette
from starlette.routing import Route, Mount
from starlette.responses import JSONResponse
import uvicorn
import threading
from fastmcp import FastMCP
import os
from typing import Optional, List
from habanero import Crossref, counts, cn

mcp = FastMCP("habanero-crossref")


@mcp.tool()
def search_works(
    query: Optional[str] = None,
    doi: Optional[str] = None,
    filter: Optional[List[str]] = None,
    limit: int = 20,
    offset: int = 0,
    sort: Optional[str] = None,
    order: Optional[str] = None,
    select: Optional[List[str]] = None,
    mailto: Optional[str] = None,
) -> dict:
    """Search Crossref works (articles, books, datasets, etc.) using the /works route.
    Use this when the user wants to find publications by query terms, DOI, author,
    title, journal, funder, or date range. Supports rich filtering, sorting, and pagination.
    This is the primary search tool for academic literature discovery."""
    cr = Crossref(mailto=mailto) if mailto else Crossref()

    kwargs = {}
    if query:
        kwargs["query"] = query
    if doi:
        kwargs["ids"] = doi
    if filter:
        # Convert list of 'key:value' strings to dict for habanero
        filter_dict = {}
        for f in filter:
            if ":" in f:
                k, v = f.split(":", 1)
                filter_dict[k] = v
        kwargs["filter"] = filter_dict
    if sort:
        kwargs["sort"] = sort
    if order:
        kwargs["order"] = order
    if select:
        kwargs["select"] = select

    kwargs["limit"] = limit
    kwargs["offset"] = offset

    result = cr.works(**kwargs)
    return result


@mcp.tool()
def get_publication_metadata(
    ids: List[str],
    select: Optional[List[str]] = None,
    mailto: Optional[str] = None,
) -> dict:
    """Retrieve full metadata for one or more specific publications using their DOIs
    via the Crossref /works route. Use this when you have known DOIs and need detailed
    bibliographic information like authors, abstract, references, funding, license, or
    publication dates."""
    cr = Crossref(mailto=mailto) if mailto else Crossref()

    kwargs = {"ids": ids}
    if select:
        kwargs["select"] = select

    result = cr.works(**kwargs)
    return result


@mcp.tool()
def get_citation_count(
    doi: str,
    mailto: Optional[str] = None,
) -> dict:
    """Retrieve the citation count for a specific publication by its DOI. Use this
    when the user wants to know how many times a paper has been cited according to
    Crossref."""
    try:
        count = counts.citation_count(doi=doi, mailto=mailto)
        return {"doi": doi, "citation_count": count}
    except Exception as e:
        return {"doi": doi, "error": str(e)}


@mcp.tool()
def get_citation_format(
    doi: str,
    format: str = "bibtex",
    style: str = "apa",
    locale: str = "en-US",
) -> dict:
    """Retrieve a citation for a DOI in a specific format using content negotiation.
    Use this when the user wants a formatted reference in BibTeX, RIS, APA, Chicago,
    MLA, or another citation style. Supports all major citation formats and CSL styles."""
    try:
        result = cn.content_negotiation(
            ids=doi,
            format=format,
            style=style,
            locale=locale,
        )
        return {"doi": doi, "format": format, "style": style, "citation": result}
    except Exception as e:
        return {"doi": doi, "error": str(e)}


@mcp.tool()
def search_members_funders_journals(
    route: str,
    ids: Optional[List[str]] = None,
    query: Optional[str] = None,
    limit: int = 20,
    offset: int = 0,
    mailto: Optional[str] = None,
) -> dict:
    """Search Crossref members, funders, journals, prefixes, licenses, or types.
    Use this to discover publishers (members), funding organizations (funders),
    or journal information, or to look up publication types and license details
    available in Crossref."""
    cr = Crossref(mailto=mailto) if mailto else Crossref()

    valid_routes = ["members", "funders", "journals", "prefixes", "licenses", "types"]
    if route not in valid_routes:
        return {"error": f"Invalid route '{route}'. Must be one of: {valid_routes}"}

    kwargs = {}
    if ids:
        kwargs["ids"] = ids
    if query:
        kwargs["query"] = query
    kwargs["limit"] = limit
    kwargs["offset"] = offset

    route_method = getattr(cr, route)
    result = route_method(**kwargs)
    return result


@mcp.tool()
def get_doi_agency(
    ids: List[str],
    mailto: Optional[str] = None,
) -> dict:
    """Determine the registration agency (e.g. Crossref, DataCite, ORCID) responsible
    for minting one or more DOIs. Use this when you need to verify who registered a
    DOI or when routing DOI resolution logic."""
    cr = Crossref(mailto=mailto) if mailto else Crossref()

    try:
        result = cr.registration_agency(ids=ids)
        return {"results": result}
    except Exception as e:
        return {"error": str(e)}


@mcp.tool()
def get_random_dois(
    count: int = 10,
    mailto: Optional[str] = None,
) -> dict:
    """Retrieve a set of random DOIs from Crossref. Use this for sampling, testing,
    demonstrating API features, or when the user wants to explore random publications
    in the Crossref database."""
    cr = Crossref(mailto=mailto) if mailto else Crossref()

    try:
        result = cr.random_dois(sample=count)
        return {"count": len(result), "dois": result}
    except Exception as e:
        return {"error": str(e)}


@mcp.tool()
def list_citation_styles(
    mailto: Optional[str] = None,
) -> dict:
    """Retrieve all available CSL (Citation Style Language) styles supported by
    Crossref content negotiation. Use this when the user wants to know what citation
    formats or styles are available before calling get_citation_format, or to let
    the user pick a specific academic style."""
    try:
        styles = cn.csl_styles()
        if isinstance(styles, list):
            return {"count": len(styles), "styles": styles}
        return {"styles": styles}
    except Exception as e:
        return {"error": str(e)}




_SERVER_SLUG = "habanero"

def _track(tool_name: str, ua: str = ""):
    try:
        import urllib.request, json as _json
        data = _json.dumps({"slug": _SERVER_SLUG, "event": "tool_call", "tool": tool_name, "user_agent": ua}).encode()
        req = urllib.request.Request("https://www.volspan.dev/api/analytics/event", data=data, headers={"Content-Type": "application/json"})
        urllib.request.urlopen(req, timeout=1)
    except Exception:
        pass

async def health(request):
    return JSONResponse({"status": "ok", "server": mcp.name})

async def tools(request):
    registered = await mcp.list_tools()
    tool_list = [{"name": t.name, "description": t.description or ""} for t in registered]
    return JSONResponse({"tools": tool_list, "count": len(tool_list)})

sse_app = mcp.http_app(transport="sse")

app = Starlette(
    routes=[
        Route("/health", health),
        Route("/tools", tools),
        Mount("/", sse_app),
    ],
    lifespan=sse_app.lifespan,
)
if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", 8000)))
