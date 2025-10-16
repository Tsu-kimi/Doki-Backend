from fastapi import FastAPI

app = FastAPI(title="Doki Backend")

@app.get("/")
async def root():
    return {"message": "Doki Backend up"}
