from pathlib import Path

from utils.report_parsers import (
    parse_neuromuscolare_html,
)


percorso = Path(
    "Neuromuscolare T0 primavera Empoli FC.html"
)

html = percorso.read_text(
    encoding="utf-8"
)

risultato = parse_neuromuscolare_html(
    html
)

print(
    "Sessioni:",
    risultato["numero_sessioni"],
)

print(
    "Risultati:",
    risultato["numero_risultati"],
)

for sessione in risultato[
    "sessioni"
][:5]:
    print()
    print(
        sessione["data"],
        "-",
        sessione["atleta"],
    )

    print(
        "Peso:",
        sessione["peso_kg"],
    )

    print(
        "Altezza:",
        sessione["altezza_cm"],
    )

    for test in sessione[
        "risultati"
    ]:
        print(
            test["nome_test"],
            test["lato"],
            test["valore"],
        )