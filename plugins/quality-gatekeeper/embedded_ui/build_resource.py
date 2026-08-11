from pathlib import Path


directory = Path(__file__).resolve().parent
shell = (directory / "report-shell.html").read_text(encoding="utf-8")
script = (directory / "report.ts").read_text(encoding="utf-8")
output = shell.replace("<!-- QUALITY_SCRIPT -->", script.replace("</script>", "<\\/script>"))
(directory / "report-v1.html").write_text(output, encoding="utf-8")
print((directory / "report-v1.html").resolve())
