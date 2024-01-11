"""
innerverz 서비스를 위해서 수정한 dockerfile 들을 배포.
배포 후에는 반드시 커밋 및 푸시 필요.
또한 배포의 타깃은
"""
import asyncio
import dataclasses
import os
from textwrap import dedent

TRUE_LIKE_STR_SET = {"true", "1", "t", "y", "yes", "yeah", "yup", "certainly", "uh-huh"}


@dataclasses.dataclass
class CONTROLS:
    DRYRUN = os.environ.get("DRYRUN") in TRUE_LIKE_STR_SET
    ASYNC = os.environ.get("ASYNC") in TRUE_LIKE_STR_SET
    BUILD_ALL = os.environ.get("BUILD_ALL") in TRUE_LIKE_STR_SET


INVZ_CUSTOMIZED_PYTHON_DOCKERFILE = [
    "3.11/bullseye/Dockerfile",
]
CUSTOMIZED_SUFFIX = "--invz-cust"
REGION = "us-east-1"
ECR_REGISTRY = f"346614530986.dkr.ecr.{REGION}.amazonaws.com"


async def run_command_with_env(cmd, env_vars):
    # Create a new environment dictionary
    new_env = os.environ.copy()
    new_env.update(env_vars)

    # Run the command
    process = await asyncio.create_subprocess_shell(
        cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        env=new_env
    )

    # Wait for the command to complete
    stdout, stderr = await process.communicate()

    return stdout.decode(), stderr.decode()


def dockerfile_to_tag(dockerfile_str: str) -> str:
    return "-".join(dockerfile_str.split("/")[:-1]) + CUSTOMIZED_SUFFIX


def form_docker_build_and_push_cmd(dockerfile, tag):
    image = f"{ECR_REGISTRY}/python:{tag}"

    cmd_form = dedent(f"""\
    docker pull {image}
    docker build -f {dockerfile} -t {image} .
    docker push {image}
    """)
    return cmd_form


async def _gather_job(cmds):
    return await asyncio.gather(*[run_command_with_env(cmd, {}) for cmd in cmds])


def get_target_dockerfiles(build_all: bool):
    if build_all:
        return INVZ_CUSTOMIZED_PYTHON_DOCKERFILE
    all_diffs, stderr = asyncio.run(run_command_with_env("git diff --name-only", {}))
    print(f"all git diffs. `{all_diffs}`")
    return [
        d for d in all_diffs.split("\n")
        if d in INVZ_CUSTOMIZED_PYTHON_DOCKERFILE
    ]


if __name__ == '__main__':
    target_dockerfiles = []
    docker_login_cmd = (f"aws ecr get-login-password --region {REGION}"
                        f" | docker login --username AWS --password-stdin {ECR_REGISTRY}")
    print("asyncio.run(run_command_with_env(docker_login_cmd, {}))")
    print("docker_login_cmd", docker_login_cmd)
    if not os.environ.get("dryrun"):
        print(asyncio.run(run_command_with_env(docker_login_cmd, {})))

    docker_build_and_push_cmds = [
        form_docker_build_and_push_cmd(dockerfile=dockerfile, tag=dockerfile_to_tag(dockerfile))
        for dockerfile in target_dockerfiles
    ]
    print(docker_build_and_push_cmds)
    print("asyncio.gather(*[run_command_with_env(cmd, {}) for cmd in docker_build_and_push_cmds])")
    if os.environ.get("dryrun"):
        pass
    elif os.environ.get("async"):
        asyncio.run(_gather_job(docker_build_and_push_cmds))
    else:
        for cmd in docker_build_and_push_cmds:
            os.system(cmd)
