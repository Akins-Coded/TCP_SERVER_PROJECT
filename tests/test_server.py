import pytest
from server import search_in_file
from client import send_query

def test_search_in_file():
    query = "TestQuery"
    result = search_in_file(query)
    assert result in ["STRING EXISTS", "STRING NOT FOUND"]

def test_query_handling():
    query = "TestQuery"
    response = send_query(query)
    assert response in ["STRING EXISTS", "STRING NOT FOUND"]
    
