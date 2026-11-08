"""Compile a bounded declarative program into an inspectable JSON artifact."""
import argparse
import json
from pathlib import Path
from tools.assemble_publication import parse
from tools.runtime.engine import compile_program, inspection, canonical


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source',type=Path)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    try:
        raw=args.source.read_bytes()
        if len(raw)>65536:raise ValueError('Program exceeds 64 KiB')
        result=inspection(compile_program(parse(raw)))
        if args.output.resolve()==args.source.resolve():raise ValueError('Output must not overwrite source')
        args.output.parent.mkdir(parents=True,exist_ok=True)
        args.output.write_bytes(canonical(result))
        print(json.dumps({'sourceDigest':result['sourceDigest'],'implementation':result['implementation']}))
    except (ValueError,OSError,RecursionError):
        parser.exit(1,'Reference compilation failed; inspect the local source and version pins.\n')


if __name__=='__main__':main()
