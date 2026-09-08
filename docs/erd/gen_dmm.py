#!/usr/bin/env python3
"""Generate a Luna Modeler .dmm (PostgreSQL) project for Allergy AI Companion."""
import json, uuid, time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
DMM_OUT = Path(__file__).resolve().parent / "allergy_ai.dmm"
SCHEMA_OUT = REPO_ROOT / "backend" / "db" / "init" / "01_schema.sql"

def uid(): return str(uuid.uuid4())

# ---- declarative schema -------------------------------------------------
# col: (name, datatype, param, nn, extra)  extra dict: pk, fk_to=(table,onDelete), default, comment
def C(name, dt, param="", nn=True, pk=False, fk=None, default="", comment=""):
    return dict(name=name, dt=dt, param=param, nn=nn, pk=pk, fk=fk, default=default, comment=comment)

TS = ("timestamp without time zone", "", True)
def pk_id(): return C("id", "serial", nn=True, pk=True)
def created(): return C("created_at", "timestamp without time zone", default="now()")
def updated(): return C("updated_at", "timestamp without time zone", default="now()")

SCHEMA = {
 "users": [
    pk_id(),
    C("email", "character varying", "255"),
    C("password_hash", "character varying", "255"),
    C("latitude", "numeric", "9,6", nn=False),
    C("longitude", "numeric", "9,6", nn=False),
    created(), updated(),
 ],
 "user_allergies": [
    pk_id(),
    C("user_id", "integer", fk=("users", "Cascade")),
    C("allergen", "character varying", "30", comment="TREE_POLLEN|GRASS_POLLEN|WEED_POLLEN|PM25|PM10|DUST|MOLD|OTHER"),
    C("severity", "character varying", "10", comment="MILD|MODERATE|SEVERE"),
    created(),
 ],
 "conversations": [
    pk_id(),
    C("user_id", "integer", fk=("users", "Cascade")),
    C("status", "character varying", "12", default="'ACTIVE'", comment="ACTIVE|COMPLETED|ABANDONED"),
    created(), updated(),
 ],
 "messages": [
    pk_id(),
    C("conversation_id", "integer", fk=("conversations", "Cascade")),
    C("role", "character varying", "10", comment="USER|ASSISTANT|SYSTEM"),
    C("content", "text"),
    created(),
 ],
 "symptom_events": [
    pk_id(),
    C("user_id", "integer", fk=("users", "Cascade")),
    C("conversation_id", "integer", nn=False, fk=("conversations", "Set null")),
    C("symptoms", "jsonb", comment="list[str], e.g. sneezing, itchy_eyes"),
    C("severity", "integer", nn=False, comment="0-10"),
    C("duration", "character varying", "50", nn=False),
    C("possible_trigger", "character varying", "50", nn=False),
    C("breathing_difficulty", "boolean", default="false"),
    C("airway_swelling", "boolean", default="false"),
    created(),
 ],
 "triage_results": [
    pk_id(),
    C("symptom_event_id", "integer", fk=("symptom_events", "Cascade")),
    C("risk_level", "character varying", "12", comment="LOW|MODERATE|EMERGENCY"),
    C("recommendation", "text", nn=False),
    C("rule_version", "character varying", "20", nn=False),
    created(),
 ],
 "environment_snapshots": [
    pk_id(),
    C("latitude", "numeric", "9,6"),
    C("longitude", "numeric", "9,6"),
    C("tree_pollen", "character varying", "10", nn=False, comment="LOW|MODERATE|HIGH"),
    C("grass_pollen", "character varying", "10", nn=False),
    C("weed_pollen", "character varying", "10", nn=False),
    C("pm25", "numeric", "6,2", nn=False),
    C("pm10", "numeric", "6,2", nn=False),
    C("temperature", "numeric", "5,2", nn=False),
    C("humidity", "numeric", "5,2", nn=False),
    C("wind_speed", "numeric", "5,2", nn=False),
    C("risk_level", "character varying", "12", nn=False, comment="LOW|MODERATE|HIGH"),
    C("captured_at", "timestamp without time zone", default="now()"),
 ],
 "alerts": [
    pk_id(),
    C("user_id", "integer", fk=("users", "Cascade")),
    C("environment_snapshot_id", "integer", nn=False, fk=("environment_snapshots", "Set null")),
    C("risk_level", "character varying", "12", comment="LOW|MODERATE|HIGH|EMERGENCY"),
    C("alert_type", "character varying", "15", comment="POLLEN|AIR_QUALITY|WEATHER|GENERAL"),
    C("message", "text"),
    C("is_read", "boolean", default="false"),
    created(),
 ],
 "hospital_searches": [
    pk_id(),
    C("user_id", "integer", fk=("users", "Cascade")),
    C("latitude", "numeric", "9,6"),
    C("longitude", "numeric", "9,6"),
    C("specialty", "character varying", "40", nn=False),
    created(),
 ],
 "hospital_results": [
    pk_id(),
    C("hospital_search_id", "integer", fk=("hospital_searches", "Cascade")),
    C("name", "character varying", "200"),
    C("address", "character varying", "300", nn=False),
    C("distance_m", "integer", nn=False),
    C("specialty", "character varying", "40", nn=False),
    C("is_open", "boolean", nn=False),
    C("phone", "character varying", "40", nn=False),
    C("place_id", "character varying", "120", nn=False),
    C("rank", "integer", nn=False),
    created(),
 ],
}

# grid positions (x,y) per table
POS = {
 "users": (60, 60), "user_allergies": (60, 320),
 "conversations": (340, 60), "messages": (620, 60),
 "symptom_events": (340, 320), "triage_results": (340, 640),
 "environment_snapshots": (900, 60), "alerts": (900, 420),
 "hospital_searches": (620, 640), "hospital_results": (900, 780),
}
COLORS = ["#1976d2","#9c27b0","#2e7d32","#00838f","#c62828","#6d4c41",
          "#455a64","#ef6c00","#5e35b1","#00695c"]

# ---- build --------------------------------------------------------------
tables, relations = {}, {}
tname_to_id, tname_pk = {}, {}   # table name -> table uuid, pk col uuid + key uuid

# first pass: create tables, cols, pk keys
built = {}
for tname, cols in SCHEMA.items():
    tid = uid()
    tname_to_id[tname] = tid
    colobjs, pk_colid = [], None
    for c in cols:
        cid = uid()
        colobjs.append(dict(
            data="", id=cid, name=c["name"], datatype=c["dt"], param=c["param"],
            pk=c["pk"], nn=c["nn"], comment=c["comment"], defaultvalue=c["default"],
            collation="", fk=bool(c["fk"]), after="",
            pg=dict(generatedIdentity="no", storage="", compression=""),
            list=False, estimatedSize="",
        ))
        c["_cid"] = cid
        if c["pk"]: pk_colid = cid
    keyid = uid()
    keys = [dict(id=keyid, isPk=True, name=f"{tname}_pkey",
                 cols=[dict(id=uid(), colid=pk_colid)])] if pk_colid else []
    tname_pk[tname] = (pk_colid, keyid)
    built[tname] = dict(_cols=cols, _tid=tid, _colobjs=colobjs, _keyid=keyid)
    tables[tid] = dict(
        lines=[], embeddable=False, objectType="table",
        pg=dict(tablespace="", inherits="", storageParameters="", partition="",
                rowsecurity=False, partitionNames=[], schema="public"),
        desc="", id=tid, name=tname, cols=colobjs, relations=[], keys=keys,
        indexes=[], estimatedSize="", visible=True, generate=True,
        generateCustomCode=True, customCode="",
    )

# second pass: relations for FKs
for tname, cols in SCHEMA.items():
    child_tid = tname_to_id[tname]
    for c in cols:
        if not c["fk"]: continue
        parent_name, on_del = c["fk"]
        parent_tid = tname_to_id[parent_name]
        parent_colid, parent_keyid = tname_pk[parent_name]
        rid = uid()
        relations[rid] = dict(
            id=rid, type="non-identifying",
            cols=[dict(id=uid(), parentcol=parent_colid, childcol=c["_cid"])],
            child=child_tid, parent=parent_tid,
            c_mp="true", c_mch="true", c_ch="many", c_p="one", c_cp="", c_cch="",
            name=f"{tname}_{c['name']}_fkey", desc="", parent_key=parent_keyid,
            ri_pd=on_del, ri_pu="No action", generate=True, generateCustomCode=True,
            customCode="", relationColor="transparent", linegraphics="default",
        )
        tables[child_tid]["relations"].append(rid)
        tables[parent_tid]["relations"].append(rid)

# diagram
diagram_id = uid()
note_id = uid()
diagram_items = {}
for i, (tname, tid) in enumerate(tname_to_id.items()):
    x, y = POS[tname]
    ncols = len(SCHEMA[tname])
    diagram_items[tid] = dict(
        x=x, y=y, gHeight=30 + 20 * ncols, gWidth=190,
        background=COLORS[i % len(COLORS)], color="#ffffff",
        referencedItemId=tid, resized=False, autoExpand=True, backgroundOpacity="10",
    )
diagram_items[note_id] = dict(
    x=60, y=760, gHeight=70, gWidth=260, background="#ffd54f", color="#000000",
    referencedItemId=note_id, resized=False, autoExpand=True, backgroundOpacity="10",
)

notes = {note_id: dict(id=note_id, visible=True, name="Title",
                       desc="<h1>Allergy AI Companion</h1><p>Environment monitoring, AI symptom triage, hospital finder.</p>",
                       lines=[], type="Note")}

diagram = dict(
    id=diagram_id, lineColor="transparent", description="",
    diagramItems=diagram_items, isOpen=True, main=True, name="Main diagram",
    keysgraphics=False, linegraphics="detailed", zoom=0.8, background="transparent",
    scroll=dict(x=0, y=0), type="erd",
    showEstimatedSize=False, showSchemaContainer=False, showEmbeddedInParents=True,
    showCardinalityCaptions=False, showRelationshipNames=False, showLineCaptions=True,
    showColumns=True, showColumnDataTypes=True, showSampleData=False,
    showTableIndexes=False, showTableDescriptions=False, showRelations=True,
    showHorizontal=False, showDescriptions=True, showIndicators=False,
    showProgress=False, showIndicatorCaptions=False, backgroundImage="na",
    descriptionsColor="transparent", boxSize="0", boxSpacing="2", boxAlign="center",
    lineWidth="2", embeddedSpacing="2", showLabels=True, showMainIcon=True,
    showCustomizations=False, showExportDimensions=False, showCompleted=True,
)

model = dict(
    connectionId=uid(), connectionVersion="PostgreSQL 16",
    activeDiagram=diagram_id, caseConvention="under", color="transparent",
    def_coltopk=True, desc="AI-powered allergy monitoring, symptom triage and hospital finder.",
    id=uid(), isDirty=False, name="Allergy AI Companion",
    parentTableInFkCols=True, path="", replaceSpace="_", sideSelections=True,
    storedin=dict(major=11, minor=0, extra=0),
    laststoredin=dict(major=11, minor=2, extra=0),
    type="PG", version=1, lastSaved=int(time.time() * 1000),
    pg=dict(schema="public"),
    sqlSettings=dict(wrapLines=True, wrapOffset=80, indent=True,
        indentationString="spaces", indentationSize=2, limitItemsOnLine=True,
        maxListItemsOnLine=3, statementDelimiter=";", routineDelimiter=";",
        keywordCase="upper", identiferCase="original", includeSchema="always",
        quotationExistance="if_needed", includeGeneratedNames="always"),
    nameAutoGeneration=dict(keys=True, indexes=True, relations=True),
    writeFileParam=False, authorName="Ismoiljon", companyDetails="", companyUrl="",
    synchronizationSettings=dict(preserveData="no_data_handled",
        ignoreSystemDefaults="yes", includeWarnings="yes", includeCreationSql="no"),
    modelHTMLReportDir="",
)

doc = dict(
    tables=tables, relations=relations, notes=notes, lines={}, model=model,
    otherObjects={}, diagrams={diagram_id: diagram}, diagramsOrder=[],
    order=list(tname_to_id.values()), collapsedTreeItems=[], reverseStats={},
)

out = DMM_OUT
with open(out, "w", encoding="utf-8") as f:
    json.dump(doc, f, indent=1)
print(f"wrote {out}: {len(tables)} tables, {len(relations)} relations")

# ---- also emit backend/db/init/01_schema.sql ----------------------------
def sql_type(c):
    dt, p = c["dt"], c["param"]
    if dt == "serial": return "SERIAL"
    if dt == "character varying": return f"VARCHAR({p})" if p else "VARCHAR"
    if dt == "numeric": return f"NUMERIC({p})" if p else "NUMERIC"
    if dt == "timestamp without time zone": return "TIMESTAMP"
    return dt.upper()

lines = ["-- Allergy AI Companion — PostgreSQL schema (generated from docs/erd/gen_dmm.py)",
         "-- Source of truth for the ERD is docs/erd/allergy_ai.dmm (open in Luna Modeler).", ""]
for tname, cols in SCHEMA.items():
    lines.append(f"CREATE TABLE {tname} (")
    body, fks = [], []
    for c in cols:
        seg = f"    {c['name']} {sql_type(c)}"
        if c["pk"]: seg += " PRIMARY KEY"
        if c["nn"] and not c["pk"]: seg += " NOT NULL"
        if c["default"]: seg += f" DEFAULT {c['default']}"
        body.append(seg)
        if c["fk"]:
            pn, od = c["fk"]
            fks.append(f"    FOREIGN KEY ({c['name']}) REFERENCES {pn}(id) ON DELETE {od.upper().replace('NO ACTION','NO ACTION')}")
    if tname == "users":
        body.append("    UNIQUE (email)")
    lines.append(",\n".join(body + fks))
    lines.append(");\n")
with open(SCHEMA_OUT, "w", encoding="utf-8") as f:
    f.write("\n".join(lines))
print(f"wrote {SCHEMA_OUT}")
