"""Writes the intents and dialogs for the languages Emkay ships besides
English and Danish (those are in locale/ by hand), so they can be reviewed
and corrected in one place. Run from the repository root:

    python tools/translations.py
"""
import json
from pathlib import Path

KINDS = ("stt", "tts", "translate", "wikipedia", "models", "store", "packages",
         "pyodide", "github", "weather", "radio")

T = {
"de-DE": {
 "name": "Wächter", "description": "Sagt, was der Assistent heute nach draußen geschickt hat und wer hört, was du sagst, aus seinem Netzwerkprotokoll.",
 "examples": ["Was hast du heute nach draußen geschickt?", "Wer hört, was ich sage?"],
 "sent_today.intent": ["was hast du heute (nach draußen|ins internet) geschickt", "was hast du heute kontaktiert", "mit wem hast du heute gesprochen", "welche dienste hast du heute benutzt"],
 "who_hears_me.intent": ["wer hört was ich sage", "wohin geht meine (stimme|sprache)", "an wen schickst du meine (stimme|sprache)", "wer hört mit", "wo wird meine sprache erkannt"],
 "sent_today": "Heute habe ich {count} Dienste kontaktiert: {list}.",
 "sent_today_more": "Heute habe ich {count} Dienste kontaktiert. Am meisten: {list}, und {rest} weitere. Das Netzwerkprotokoll im Menü hat alle.",
 "times": "{service} {count} Mal", "times_one": "{service} einmal", "and": "und",
 "sent_nothing": "Ich habe heute nichts nach draußen geschickt.",
 "no_log": "Ich führe hier kein Netzwerkprotokoll, also kann ich nicht sagen, was hinausging. Frag mich, wer hört, was du sagst, dann sage ich, was meine Einstellungen sagen.",
 "stt_local": "Nur ich. Was du sagst, wird hier auf dem Gerät von {module} erkannt und verlässt es nicht.",
 "stt_browser": "Die Spracherkennung deines Browsers hört es: in Chrome ist das Google, in Safari Apple. Wenn die Sprache hier bleiben soll, wähle in den Einstellungen ein lokales Spracherkennungs-Plugin.",
 "stt_remote_seen": "Was du sagst, geht zur Erkennung an {hosts}, über {module}. Das ist der öffentliche Server von OpenVoiceOS; wenn die Sprache hier bleiben soll, wähle in den Einstellungen ein lokales Plugin.",
 "stt_remote": "Was du sagst, geht zur Erkennung an einen Server, über {module}. Wenn die Sprache hier bleiben soll, wähle in den Einstellungen ein lokales Plugin.",
 "kinds": ["Spracherkennung", "die Stimme", "Übersetzung", "Wikipedia", "Modell-Downloads", "der Skill-Store", "Paketinstallationen", "Pyodide-Pakete", "GitHub", "das Wetter", "Radio und Nachrichten"],
},
"nl-NL": {
 "name": "Wachter", "description": "Vertelt wat de assistent vandaag naar buiten heeft gestuurd en wie hoort wat je zegt, uit zijn netwerklogboek.",
 "examples": ["Wat heb je vandaag naar buiten gestuurd?", "Wie hoort wat ik zeg?"],
 "sent_today.intent": ["wat heb je vandaag (naar buiten|naar het internet) gestuurd", "wat heb je vandaag benaderd", "met wie heb je vandaag gepraat", "welke diensten heb je vandaag gebruikt"],
 "who_hears_me.intent": ["wie hoort wat ik zeg", "waar gaat mijn (stem|spraak) naartoe", "naar wie stuur je mijn (stem|spraak)", "wie luistert mee", "waar wordt mijn spraak herkend"],
 "sent_today": "Vandaag heb ik {count} diensten benaderd: {list}.",
 "sent_today_more": "Vandaag heb ik {count} diensten benaderd. Het meest: {list}, en nog {rest}. Het netwerklogboek in het menu heeft ze allemaal.",
 "times": "{service} {count} keer", "times_one": "{service} één keer", "and": "en",
 "sent_nothing": "Ik heb vandaag niets naar buiten gestuurd.",
 "no_log": "Ik houd hier geen netwerklogboek bij, dus ik kan niet zeggen wat er naar buiten ging. Vraag me wie hoort wat je zegt, dan vertel ik wat mijn instellingen zeggen.",
 "stt_local": "Alleen ik. Wat je zegt wordt hier op het apparaat herkend door {module}, en verlaat het niet.",
 "stt_browser": "De spraakherkenning van je browser hoort het: in Chrome is dat Google, in Safari Apple. Kies in de instellingen een lokale spraakherkenning als je spraak hier moet blijven.",
 "stt_remote_seen": "Wat je zegt gaat naar {hosts} om herkend te worden, via {module}. Dat is de openbare server van OpenVoiceOS; kies in de instellingen een lokale plugin als je spraak hier moet blijven.",
 "stt_remote": "Wat je zegt gaat naar een server om herkend te worden, via {module}. Kies in de instellingen een lokale plugin als je spraak hier moet blijven.",
 "kinds": ["spraakherkenning", "de stem", "vertaling", "Wikipedia", "modeldownloads", "de skillwinkel", "pakketinstallaties", "Pyodide-pakketten", "GitHub", "het weer", "radio en nieuws"],
},
"fr-FR": {
 "name": "Gardien", "description": "Dit ce que l'assistant a envoyé dehors aujourd'hui et qui entend ce que tu dis, d'après son journal réseau.",
 "examples": ["Qu'as-tu envoyé dehors aujourd'hui ?", "Qui entend ce que je dis ?"],
 "sent_today.intent": ["qu'as-tu envoyé (dehors|sur internet) aujourd'hui", "qu'as-tu contacté aujourd'hui", "à qui as-tu parlé aujourd'hui", "quels services as-tu utilisés aujourd'hui"],
 "who_hears_me.intent": ["qui entend ce que je dis", "où va ma (voix|parole)", "à qui envoies-tu ma (voix|parole)", "qui m'écoute", "où ma parole est-elle reconnue"],
 "sent_today": "Aujourd'hui, j'ai contacté {count} services : {list}.",
 "sent_today_more": "Aujourd'hui, j'ai contacté {count} services. Les plus utilisés : {list}, et {rest} autres. Le journal réseau du menu les a tous.",
 "times": "{service} {count} fois", "times_one": "{service} une fois", "and": "et",
 "sent_nothing": "Je n'ai rien envoyé dehors aujourd'hui.",
 "no_log": "Je ne tiens pas de journal réseau ici, je ne peux donc pas dire ce qui est sorti. Demande-moi qui entend ce que tu dis, et je te dirai ce que disent mes réglages.",
 "stt_local": "Moi seul. Ce que tu dis est reconnu ici, sur l'appareil, par {module}, et ne le quitte pas.",
 "stt_browser": "La reconnaissance vocale de ton navigateur l'entend : dans Chrome, c'est Google, dans Safari, Apple. Pour que ta parole reste ici, choisis une reconnaissance vocale locale dans les réglages.",
 "stt_remote_seen": "Ce que tu dis part vers {hosts} pour être reconnu, via {module}. C'est le serveur public d'OpenVoiceOS ; pour que ta parole reste ici, choisis un plugin local dans les réglages.",
 "stt_remote": "Ce que tu dis part vers un serveur pour être reconnu, via {module}. Pour que ta parole reste ici, choisis un plugin local dans les réglages.",
 "kinds": ["la reconnaissance vocale", "la voix", "la traduction", "Wikipédia", "les téléchargements de modèles", "la boutique de skills", "les installations de paquets", "les paquets Pyodide", "GitHub", "la météo", "la radio et les infos"],
},
"es-ES": {
 "name": "Guardián", "description": "Dice qué ha enviado fuera el asistente hoy y quién oye lo que dices, según su registro de red.",
 "examples": ["¿Qué has enviado fuera hoy?", "¿Quién oye lo que digo?"],
 "sent_today.intent": ["qué has enviado (fuera|a internet) hoy", "qué has contactado hoy", "con quién has hablado hoy", "qué servicios has usado hoy"],
 "who_hears_me.intent": ["quién oye lo que digo", "a dónde va mi (voz|habla)", "a quién envías mi (voz|habla)", "quién me escucha", "dónde se reconoce mi voz"],
 "sent_today": "Hoy he contactado {count} servicios: {list}.",
 "sent_today_more": "Hoy he contactado {count} servicios. Los más usados: {list}, y {rest} más. El registro de red del menú los tiene todos.",
 "times": "{service} {count} veces", "times_one": "{service} una vez", "and": "y",
 "sent_nothing": "Hoy no he enviado nada fuera.",
 "no_log": "Aquí no llevo un registro de red, así que no puedo decir qué ha salido. Pregúntame quién oye lo que dices y te diré lo que dicen mis ajustes.",
 "stt_local": "Solo yo. Lo que dices se reconoce aquí, en el dispositivo, con {module}, y no sale de él.",
 "stt_browser": "Lo oye el reconocimiento de voz de tu navegador: en Chrome es Google, en Safari Apple. Para que tu voz se quede aquí, elige un reconocimiento de voz local en los ajustes.",
 "stt_remote_seen": "Lo que dices va a {hosts} para reconocerlo, con {module}. Es el servidor público de OpenVoiceOS; para que tu voz se quede aquí, elige un plugin local en los ajustes.",
 "stt_remote": "Lo que dices va a un servidor para reconocerlo, con {module}. Para que tu voz se quede aquí, elige un plugin local en los ajustes.",
 "kinds": ["el reconocimiento de voz", "la voz", "la traducción", "Wikipedia", "las descargas de modelos", "la tienda de skills", "las instalaciones de paquetes", "los paquetes de Pyodide", "GitHub", "el tiempo", "la radio y las noticias"],
},
"it-IT": {
 "name": "Guardiano", "description": "Dice cosa ha inviato fuori oggi l'assistente e chi sente quello che dici, dal suo registro di rete.",
 "examples": ["Cosa hai inviato fuori oggi?", "Chi sente quello che dico?"],
 "sent_today.intent": ["cosa hai inviato (fuori|su internet) oggi", "cosa hai contattato oggi", "con chi hai parlato oggi", "quali servizi hai usato oggi"],
 "who_hears_me.intent": ["chi sente quello che dico", "dove va la mia voce", "a chi mandi la mia voce", "chi mi ascolta", "dove viene riconosciuta la mia voce"],
 "sent_today": "Oggi ho contattato {count} servizi: {list}.",
 "sent_today_more": "Oggi ho contattato {count} servizi. I più usati: {list}, e altri {rest}. Il registro di rete nel menu li ha tutti.",
 "times": "{service} {count} volte", "times_one": "{service} una volta", "and": "e",
 "sent_nothing": "Oggi non ho inviato niente fuori.",
 "no_log": "Qui non tengo un registro di rete, quindi non posso dire cosa è uscito. Chiedimi chi sente quello che dici e ti dirò cosa dicono le mie impostazioni.",
 "stt_local": "Solo io. Quello che dici viene riconosciuto qui sul dispositivo da {module}, e non ne esce.",
 "stt_browser": "Lo sente il riconoscimento vocale del tuo browser: in Chrome è Google, in Safari Apple. Se vuoi che la voce resti qui, scegli un riconoscimento vocale locale nelle impostazioni.",
 "stt_remote_seen": "Quello che dici va a {hosts} per essere riconosciuto, tramite {module}. È il server pubblico di OpenVoiceOS; se vuoi che la voce resti qui, scegli un plugin locale nelle impostazioni.",
 "stt_remote": "Quello che dici va a un server per essere riconosciuto, tramite {module}. Se vuoi che la voce resti qui, scegli un plugin locale nelle impostazioni.",
 "kinds": ["il riconoscimento vocale", "la voce", "la traduzione", "Wikipedia", "i download dei modelli", "il negozio di skill", "le installazioni di pacchetti", "i pacchetti Pyodide", "GitHub", "il meteo", "radio e notizie"],
},
"pt-BR": {
 "name": "Guardião", "description": "Diz o que o assistente enviou para fora hoje e quem ouve o que você diz, a partir do registro de rede.",
 "examples": ["O que você enviou para fora hoje?", "Quem ouve o que eu digo?"],
 "sent_today.intent": ["o que você enviou (para fora|para a internet) hoje", "o que você contatou hoje", "com quem você falou hoje", "quais serviços você usou hoje"],
 "who_hears_me.intent": ["quem ouve o que eu digo", "para onde vai a minha (voz|fala)", "para quem você manda a minha (voz|fala)", "quem está escutando", "onde a minha fala é reconhecida"],
 "sent_today": "Hoje contatei {count} serviços: {list}.",
 "sent_today_more": "Hoje contatei {count} serviços. Os mais usados: {list}, e mais {rest}. O registro de rede no menu tem todos.",
 "times": "{service} {count} vezes", "times_one": "{service} uma vez", "and": "e",
 "sent_nothing": "Hoje não enviei nada para fora.",
 "no_log": "Aqui eu não mantenho um registro de rede, então não sei dizer o que saiu. Pergunte quem ouve o que você diz, e eu conto o que as minhas configurações dizem.",
 "stt_local": "Só eu. O que você diz é reconhecido aqui no aparelho pelo {module}, e não sai dele.",
 "stt_browser": "O reconhecimento de voz do seu navegador ouve: no Chrome é o Google, no Safari a Apple. Para a sua fala ficar aqui, escolha um reconhecimento de voz local nas configurações.",
 "stt_remote_seen": "O que você diz vai para {hosts} para ser reconhecido, pelo {module}. É o servidor público do OpenVoiceOS; para a sua fala ficar aqui, escolha um plugin local nas configurações.",
 "stt_remote": "O que você diz vai para um servidor para ser reconhecido, pelo {module}. Para a sua fala ficar aqui, escolha um plugin local nas configurações.",
 "kinds": ["o reconhecimento de voz", "a voz", "a tradução", "a Wikipédia", "downloads de modelos", "a loja de skills", "instalações de pacotes", "pacotes do Pyodide", "o GitHub", "o tempo", "rádio e notícias"],
},
"pt-PT": {
 "name": "Guardião", "description": "Diz o que o assistente enviou para fora hoje e quem ouve o que dizes, a partir do registo de rede.",
 "examples": ["O que enviaste para fora hoje?", "Quem ouve o que eu digo?"],
 "sent_today.intent": ["o que enviaste (para fora|para a internet) hoje", "o que contactaste hoje", "com quem falaste hoje", "que serviços usaste hoje"],
 "who_hears_me.intent": ["quem ouve o que eu digo", "para onde vai a minha (voz|fala)", "a quem envias a minha (voz|fala)", "quem está a ouvir", "onde é reconhecida a minha fala"],
 "sent_today": "Hoje contactei {count} serviços: {list}.",
 "sent_today_more": "Hoje contactei {count} serviços. Os mais usados: {list}, e mais {rest}. O registo de rede no menu tem todos.",
 "times": "{service} {count} vezes", "times_one": "{service} uma vez", "and": "e",
 "sent_nothing": "Hoje não enviei nada para fora.",
 "no_log": "Aqui não mantenho um registo de rede, por isso não sei dizer o que saiu. Pergunta-me quem ouve o que dizes, e eu digo-te o que dizem as minhas definições.",
 "stt_local": "Só eu. O que dizes é reconhecido aqui no aparelho pelo {module}, e não sai dele.",
 "stt_browser": "O reconhecimento de voz do teu navegador ouve: no Chrome é a Google, no Safari a Apple. Para a tua fala ficar aqui, escolhe um reconhecimento de voz local nas definições.",
 "stt_remote_seen": "O que dizes vai para {hosts} para ser reconhecido, pelo {module}. É o servidor público do OpenVoiceOS; para a tua fala ficar aqui, escolhe um plugin local nas definições.",
 "stt_remote": "O que dizes vai para um servidor para ser reconhecido, pelo {module}. Para a tua fala ficar aqui, escolhe um plugin local nas definições.",
 "kinds": ["o reconhecimento de voz", "a voz", "a tradução", "a Wikipédia", "transferências de modelos", "a loja de skills", "instalações de pacotes", "pacotes do Pyodide", "o GitHub", "o tempo", "rádio e notícias"],
},
"ca-ES": {
 "name": "Guardià", "description": "Diu què ha enviat fora avui l'assistent i qui sent el que dius, segons el seu registre de xarxa.",
 "examples": ["Què has enviat fora avui?", "Qui sent el que dic?"],
 "sent_today.intent": ["què has enviat (fora|a internet) avui", "què has contactat avui", "amb qui has parlat avui", "quins serveis has fet servir avui"],
 "who_hears_me.intent": ["qui sent el que dic", "on va la meva veu", "a qui envies la meva veu", "qui m'escolta", "on es reconeix la meva veu"],
 "sent_today": "Avui he contactat {count} serveis: {list}.",
 "sent_today_more": "Avui he contactat {count} serveis. Els més usats: {list}, i {rest} més. El registre de xarxa del menú els té tots.",
 "times": "{service} {count} vegades", "times_one": "{service} una vegada", "and": "i",
 "sent_nothing": "Avui no he enviat res fora.",
 "no_log": "Aquí no porto cap registre de xarxa, així que no puc dir què ha sortit. Pregunta'm qui sent el que dius i et diré què diuen els meus ajustos.",
 "stt_local": "Només jo. El que dius es reconeix aquí, a l'aparell, amb {module}, i no en surt.",
 "stt_browser": "Ho sent el reconeixement de veu del navegador: a Chrome és Google, a Safari Apple. Perquè la veu es quedi aquí, tria un reconeixement de veu local als ajustos.",
 "stt_remote_seen": "El que dius va a {hosts} per ser reconegut, amb {module}. És el servidor públic d'OpenVoiceOS; perquè la veu es quedi aquí, tria un connector local als ajustos.",
 "stt_remote": "El que dius va a un servidor per ser reconegut, amb {module}. Perquè la veu es quedi aquí, tria un connector local als ajustos.",
 "kinds": ["el reconeixement de veu", "la veu", "la traducció", "la Viquipèdia", "les baixades de models", "la botiga de skills", "les instal·lacions de paquets", "els paquets de Pyodide", "GitHub", "el temps", "la ràdio i les notícies"],
},
"gl-ES": {
 "name": "Garda", "description": "Di que enviou fóra hoxe o asistente e quen oe o que dis, segundo o seu rexistro de rede.",
 "examples": ["Que enviaches fóra hoxe?", "Quen oe o que digo?"],
 "sent_today.intent": ["que enviaches (fóra|a internet) hoxe", "que contactaches hoxe", "con quen falaches hoxe", "que servizos usaches hoxe"],
 "who_hears_me.intent": ["quen oe o que digo", "a onde vai a miña voz", "a quen lle mandas a miña voz", "quen me escoita", "onde se recoñece a miña voz"],
 "sent_today": "Hoxe contactei {count} servizos: {list}.",
 "sent_today_more": "Hoxe contactei {count} servizos. Os máis usados: {list}, e {rest} máis. O rexistro de rede do menú tenos todos.",
 "times": "{service} {count} veces", "times_one": "{service} unha vez", "and": "e",
 "sent_nothing": "Hoxe non enviei nada fóra.",
 "no_log": "Aquí non levo un rexistro de rede, así que non podo dicir que saíu. Pregúntame quen oe o que dis e direiche o que din os meus axustes.",
 "stt_local": "Só eu. O que dis recoñécese aquí, no aparello, con {module}, e non sae del.",
 "stt_browser": "Oe o recoñecemento de voz do teu navegador: en Chrome é Google, en Safari Apple. Para que a túa voz quede aquí, escolle un recoñecemento de voz local nos axustes.",
 "stt_remote_seen": "O que dis vai a {hosts} para recoñecelo, con {module}. É o servidor público de OpenVoiceOS; para que a túa voz quede aquí, escolle un complemento local nos axustes.",
 "stt_remote": "O que dis vai a un servidor para recoñecelo, con {module}. Para que a túa voz quede aquí, escolle un complemento local nos axustes.",
 "kinds": ["o recoñecemento de voz", "a voz", "a tradución", "a Wikipedia", "as descargas de modelos", "a tenda de skills", "as instalacións de paquetes", "os paquetes de Pyodide", "GitHub", "o tempo", "a radio e as noticias"],
},
"eu-ES": {
 "name": "Zaindaria", "description": "Laguntzaileak gaur kanpora zer bidali duen eta esaten duzuna nork entzuten duen esaten du, bere sare-erregistroaren arabera.",
 "examples": ["Zer bidali duzu kanpora gaur?", "Nork entzuten du esaten dudana?"],
 "sent_today.intent": ["zer bidali duzu kanpora gaur", "zer bidali duzu internetera gaur", "norekin hitz egin duzu gaur", "zein zerbitzu erabili dituzu gaur"],
 "who_hears_me.intent": ["nork entzuten du esaten dudana", "nora doa nire ahotsa", "nori bidaltzen diozu nire ahotsa", "nor dago entzuten", "non ezagutzen da nire ahotsa"],
 "sent_today": "Gaur {count} zerbitzurekin jarri naiz harremanetan: {list}.",
 "sent_today_more": "Gaur {count} zerbitzurekin jarri naiz harremanetan. Gehien erabiliak: {list}, eta beste {rest}. Menuko sare-erregistroak denak ditu.",
 "times": "{service} {count} aldiz", "times_one": "{service} behin", "and": "eta",
 "sent_nothing": "Gaur ez dut ezer bidali kanpora.",
 "no_log": "Hemen ez dut sare-erregistrorik, beraz ezin dut esan zer atera den. Galdetu nork entzuten duen esaten duzuna, eta nire ezarpenek zer dioten esango dizut.",
 "stt_local": "Nik bakarrik. Esaten duzuna hemen, gailuan, {module}(e)k ezagutzen du, eta ez da handik ateratzen.",
 "stt_browser": "Zure nabigatzailearen ahots-ezagutzak entzuten du: Chromen Google da, Safarin Apple. Ahotsa hemen gera dadin, aukeratu ahots-ezagutza lokal bat ezarpenetan.",
 "stt_remote_seen": "Esaten duzuna {hosts}(e)ra doa ezagutzeko, {module} bidez. OpenVoiceOSen zerbitzari publikoa da; ahotsa hemen gera dadin, aukeratu plugin lokal bat ezarpenetan.",
 "stt_remote": "Esaten duzuna zerbitzari batera doa ezagutzeko, {module} bidez. Ahotsa hemen gera dadin, aukeratu plugin lokal bat ezarpenetan.",
 "kinds": ["ahots-ezagutza", "ahotsa", "itzulpena", "Wikipedia", "eredu-deskargak", "skill-denda", "pakete-instalazioak", "Pyodide paketeak", "GitHub", "eguraldia", "irratia eta albisteak"],
},
}

DIALOGS = ("sent_today", "sent_today_more", "times", "times_one", "and", "sent_nothing", "no_log",
           "stt_local", "stt_browser", "stt_remote_seen", "stt_remote")

for lang, d in T.items():
    loc = Path("locale", lang)
    loc.mkdir(parents=True, exist_ok=True)
    for name in ("sent_today.intent", "who_hears_me.intent"):
        (loc / name).write_text("\n".join(d[name]) + "\n", encoding="utf-8")
    for name in DIALOGS:
        (loc / f"{name}.dialog").write_text(d[name] + "\n", encoding="utf-8")
    for kind, word in zip(KINDS, d["kinds"]):
        (loc / f"kind_{kind}.dialog").write_text(word + "\n", encoding="utf-8")
    (loc / "skill.json").write_text(json.dumps({
        "skill_id": "ovos-skill-guardian.emkay-voice",
        "source": "https://github.com/emkay-voice/ovos-skill-guardian",
        "name": d["name"], "description": d["description"], "examples": d["examples"],
        "tags": ["privacy", "network", "emkay"]}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(lang)
