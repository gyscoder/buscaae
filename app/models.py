from pydantic import BaseModel, Field, validator
from typing import List, Optional
import re

class SearchParams(BaseModel):
    title: Optional[str] = Field(
        None,
        description="Book title to search for",
        example="Harry Potter"
    )
    author: Optional[str] = Field(
        None,
        description="Author name",
        example="J.K. Rowling"
    )
    publisher: Optional[str] = Field(
        None,
        description="Publisher name",
        example="Bloomsbury"
    )
    year: Optional[int] = Field(
        None,
        description="Publication year",
        example=1997,
        ge=1000,
        le=2030
    )
    filetypes: Optional[List[str]] = Field(
        None,
        description="List of file types to search for (pdf, epub, mobi)",
        example=["pdf", "epub"]
    )
    site: Optional[str] = Field(
        None,
        description="Specific site to search (e.g., archive.org)",
        example="archive.org"
    )
    frase: Optional[str] = Field(
        None,
        description="Exact phrase to search for in text",
        example='"boy who lived"'
    )

    @validator('year')
    def validate_year(cls, v):
        if v is not None and (v < 1000 or v > 2030):
            raise ValueError('Year must be between 1000 and 2030')
        return v

    @validator('filetypes', each_item=True)
    def validate_filetype(cls, v):
        allowed = ['pdf', 'epub', 'mobi', 'txt', 'djvu']
        if v.lower() not in allowed:
            raise ValueError(f'File type must be one of {allowed}')
        return v.lower()

    @validator('title', 'author', 'publisher', 'frase')
    def validate_string_fields(cls, v):
        if v is not None:
            # Remove excessive whitespace and limit length
            v = ' '.join(v.split())
            if len(v) > 200:
                raise ValueError('Field too long (max 200 characters)')
            # Basic sanitization to prevent obvious injection attempts
            if re.search(r'[<>{}]', v):
                raise ValueError('Field contains invalid characters')
        return v

    class Config:
        schema_extra = {
            "example": {
                "title": "Harry Potter and the Philosopher's Stone",
                "author": "J.K. Rowling",
                "year": 1997,
                "filetypes": ["pdf", "epub"],
                "frase": "\"boy who lived\""
            }
        }