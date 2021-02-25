from typing import Any, Dict, Literal, Union
import json
import asyncio

from rich.progress import Progress, SpinnerColumn, BarColumn, TimeElapsedColumn
from typer import Argument, echo, run, Typer, Option, Exit, FileText
from unsync import unsync
import httpx

from core.config import settings

cli = Typer()


def api_url(suffix: str):
    return f"{settings.PAPERO_SERVER}/api/v1/{suffix}"


async def template_url(
    template, data, template_server="https://demo.papero.io/templates"
):
    json_data = json.dumps(data)
    return f"{template_server}/{template}?data={json_data}"


async def post_template_job(
    client: httpx.AsyncClient, template: str, data: Dict[str, Any]
):
    return await post_job(client, await template_url(template, data), "url",)


async def post_job(client: httpx.AsyncClient, resource: str, input_type: str = "url"):
    return await client.post(
        api_url("jobs/"), json={"resource": resource, "input_type": input_type,}
    )


async def poll_for_pdf(client, job_id, task, progress):
    pdf_link = None
    while pdf_link is None:
        # echo("waiting")
        doc_req = await client.get(api_url(f"jobs/{job_id}"))
        if doc_req.status_code == 200:
            try:
                pdf_link = doc_req.json()["document"]["url"]
                progress.update(task, completed=100)
            except (KeyError, TypeError):
                await asyncio.sleep(0.3)
                continue
    return pdf_link


@unsync
async def handle_post_job(token, resource: str, input_type: str = "url"):
    async with httpx.AsyncClient(
        headers={"authorization": f"Bearer {token}"}
    ) as client:
        with Progress(
            SpinnerColumn(),
            "[progress.description]{task.description}",
            BarColumn(),
            transient=True,
        ) as progress:
            task = progress.add_task("Working", start=False)
            job_req = await post_job(client, resource, input_type)
            # job_req = await job_co
            job_id = job_req.json().get("job_id")
            pdf = await poll_for_pdf(client, job_id, task, progress)
    return pdf


@unsync
async def handle_post_template_jobs(token, template, data):
    async with httpx.AsyncClient(
        headers={"authorization": f"Bearer {token}"}
    ) as client:
        with Progress(
            SpinnerColumn(),
            "[progress.description]{task.description}",
            BarColumn(),
            transient=True,
        ) as progress:
            jobs = []
            for entry in data:
                task = progress.add_task("Working", start=False)
                job_req = await post_template_job(client, template, entry)
                job_id = job_req.json().get("job_id")
                jobs.append(poll_for_pdf(client, job_id, task, progress))
            pdfs = await asyncio.gather(*jobs)
    # breakpoint()
    return pdfs


@unsync
async def test():
    echo("Hello")


@cli.command()
def main():
    echo("Welcome to Papero CLI")
    echo("Set you API key in a environment variable named 'PAPERO_API_TOKEN'")
    echo("You can get you access token with papero login")
    echo("If you use a custom papero instance set 'PAPERO_SERVER' as well.")


@cli.command()
def login(
    email: str = Option(..., prompt=True,),
    password: str = Option(..., prompt=True, hide_input=True),
):
    """
    Login to Papero and get an access_token to use with API/CLI.
    """
    echo(f"Attempting login for {email}.")
    token_req = httpx.post(
        api_url("login/access-token"), data={"username": email, "password": password,}
    )
    if token_req.status_code != 200:
        echo("Invalid password")
        raise Exit(code=1)
    echo("Login succesful, use the following environment variable:")
    echo(f"PAPERO_API_TOKEN={token_req.json().get('access_token')}")


@cli.command()
def add_job(
    url: str = Argument(..., help="URL 🌐  to create a PDF from."),
    token: str = Argument(..., envvar="PAPERO_API_TOKEN"),
):
    """
    Add a new job to Papero via URL.
    """
    echo("Creating PDF of URL")
    echo(f"Resource: {url}")
    echo(handle_post_job(token, url, "url").result())


@cli.command()
def add_job_html(
    file: FileText = Argument(..., help="HTML-file 📄  to create a PDF from."),
    token: str = Argument(..., envvar="PAPERO_API_TOKEN"),
):
    """
    Add a new job to Papero from HTML-file.
    """
    html = file.read()
    echo("Converting PDF to HTML")
    echo(handle_post_job(token, html, "html").result())


@cli.command()
def add_job_template(
    template: str = Argument(..., help="Template to create a PDF from."),
    file: FileText = Argument(..., help="JSON-file with data for template create."),
    token: str = Argument(..., envvar="PAPERO_API_TOKEN"),
):
    """
    Add a new job to Papero from HTML-file.
    """
    data = json.loads(file.read())
    echo("Creating PDF from template with given data.")
    echo(handle_post_template_jobs(token, template, [data]).result()[0])


@cli.command()
def add_bulk_job_template(
    template: str = Argument(..., help="Template to create a PDF from."),
    file: FileText = Argument(..., help="JSON-file with data for template create."),
    token: str = Argument(..., envvar="PAPERO_API_TOKEN"),
):
    """
    Add a new job to Papero from HTML-file.
    """
    data = json.loads(file.read())
    echo("Creating PDFs from templates with given data.")
    [echo(pdf) for pdf in handle_post_template_jobs(token, template, data).result()]


if __name__ == "__main__":
    cli()
