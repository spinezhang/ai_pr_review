from setuptools import setup

setup(
    name="ai-pr-review",
    version="0.1.0",
    description="AI-powered Azure DevOps PR assistant",
    py_modules=["ai_pr_review"],
    install_requires=["anthropic>=0.39.0"],
    entry_points={
        "console_scripts": [
            "ai-pr-review=ai_pr_review:main",
        ],
    },
)
