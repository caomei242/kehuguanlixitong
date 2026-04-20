from __future__ import annotations


def test_app_module_imports():
    import strawberry_customer_management.app as app

    assert app.APP_NAME == "草莓客户管理系统"

