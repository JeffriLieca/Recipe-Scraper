

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from urllib.request import urlopen
from recipe_scrapers import scrape_html
import uuid
from urllib.parse import urlparse
from recipe_scrapers import SCRAPERS

app = FastAPI()

def is_supported_url(url: str) -> bool:
    hostname = urlparse(url).hostname or ""
    domain = hostname.replace("www.", "")
    return domain in SCRAPERS.keys()



def determine_difficulty(steps: list[str]) -> str:
    count = len(steps)
    if count <= 5:
        return "Mudah"
    elif count <= 10:
        return "Sedang"
    else:
        return "Susah"

def get_time_fallback(scraper) -> int:
    for attr in ["total_time", "cook_time", "prep_time"]:
        method = getattr(scraper, attr, None)
        if callable(method):
            try:
                time = method()
                if time:
                    return time
            except Exception:
                continue
    return 0

def safe_call(scraper, method_name: str, fallback=""):
    method = getattr(scraper, method_name, None)
    if callable(method):
        try:
            return method() or fallback
        except Exception:
            return fallback
    return fallback

def get_author_with_site(scraper, url: str) -> str:
    author = safe_call(scraper, "author", "Unknown")
    site_name = safe_call(scraper,"site_name", "Unknown")
    # site_clean = site.replace("www.", "") if site else "website"
    return f"{author} ({site_name})"

class RecipeResponse(BaseModel):
    id: str
    title: str
    author: str
    image_name: str
    description: str
    ingredient: list[str]
    steps: list[str]
    cooking_time: int
    difficulty: str


@app.get("/scrape-recipe", response_model=RecipeResponse)
def scrape_recipe(url: str):
    if not is_supported_url(url):
        raise HTTPException(status_code=400, detail="URL tidak didukung oleh recipe-scrapers.")

    try:
        html = urlopen(url).read().decode("utf-8")
        scraper = scrape_html(html, org_url=url)

        title = safe_call(scraper, "title", "Tanpa Judul")
        author = get_author_with_site(scraper, url)
        description = safe_call(scraper, "description", "Tidak ada deskripsi")
        ingredients = safe_call(scraper, "ingredients", [])
        steps = safe_call(scraper, "instructions_list", [])

        if not steps:
            raw_instructions = safe_call(scraper, "instructions", "")
            steps = [s.strip() for s in raw_instructions.split(".") if len(s.strip()) > 10]

        cooking_time = get_time_fallback(scraper)
        difficulty = determine_difficulty(steps)
        image_url = safe_call(scraper, "image", "")

        return RecipeResponse(
            id=str(uuid.uuid4()),
            title=title,
            author=author,
            image_name=image_url,
            description=description,
            ingredient=ingredients,
            steps=steps,
            cooking_time=cooking_time,
            difficulty=difficulty
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Gagal memproses link: {str(e)}")
