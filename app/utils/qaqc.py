from app.schemas.models import OneLineRequest
def check_service_size(req: OneLineRequest) -> list[str]:
    issues = []
    if req.service_amperes < 800:
        issues.append("Service size unusually small for commercial main. Confirm calculation.")
    return issues
