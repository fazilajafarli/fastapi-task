from pydantic import BaseModel, constr

class PostCreate(BaseModel):
    text: constr(max_length=1048576)  # 1MB (1,048,576 bytes)