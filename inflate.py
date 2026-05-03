import re
import sys
import os

# Starting delta value 
INITIAL_DELTA = 100

# Conditions to never inflate 
SKIP_PATTERNS = [
    re.compile(r'\bscanf\b'),
    re.compile(r'!='),
    re.compile(r'==\s*[01]\b'),
    re.compile(r'\b[01]\s*=='),
]

def should_skip(condition_str):
    for pattern in SKIP_PATTERNS:
        if pattern.search(condition_str):
            return True
    return False

def build_inflated_block(lhs, rhs, body_lines, indent):

    inner = indent + "    "
    inner2 = inner + "    "
    inner3 = inner2 + "    "

    # Pick a safe temp variable name based on lhs
    safe_lhs = re.sub(r'[^a-zA-Z0-9_]', '_', lhs.strip())
    target_var = "_target_" + safe_lhs

    lines = []
    lines.append(indent + "int " + target_var + " = " + rhs + ";")
    lines.append(indent + "for (int i = " + str(INITIAL_DELTA) + "; i >= 0; i--)")
    lines.append(indent + "{")
    lines.append(inner + "if ((" + lhs + " >= " + target_var + " - i) && (" + lhs + " <= " + target_var + " + i)){")
    lines.append(inner2 + "counter++;")
    lines.append(inner2 + "if (" + lhs + " == " + target_var + "){")
    for body_line in body_lines:
        lines.append(inner2 + "    " + body_line)
    lines.append(inner2 + "}")
    lines.append(inner + "}")
    lines.append(indent + "}")
    return lines

def extract_block(source_lines, start_idx):
    """
    Extract the body of the if-block at start_idx.
    Returns (body_lines, next_line_idx).
    body_lines is inner content with one level of indent stripped.
    """
    line = source_lines[start_idx]
    brace_depth = line.count('{') - line.count('}')

    if brace_depth == 0:
        raw = source_lines[start_idx + 1]
        base_indent = line[:len(line) - len(line.lstrip())] + "    "
        body = [raw[len(base_indent):] if raw.startswith(base_indent) else raw.lstrip()]
        return body, start_idx + 2

    raw_body = []
    j = start_idx + 1
    while j < len(source_lines) and brace_depth > 0:
        l = source_lines[j]
        brace_depth += l.count('{') - l.count('}')
        if brace_depth > 0:
            raw_body.append(l)
        j += 1

    # Strip one level of indentation relative to the if line
    base_indent = line[:len(line) - len(line.lstrip())] + "    "
    stripped = []
    for l in raw_body:
        if l.startswith(base_indent):
            stripped.append(l[len(base_indent):])
        else:
            stripped.append(l.lstrip())
    return stripped, j

def inject_counter_if_needed(source_lines):
    for line in source_lines:
        if re.match(r'\s*int\s+counter\s*[=;]', line):
            return source_lines

    last_include = -1
    for i, line in enumerate(source_lines):
        if line.strip().startswith('#include'):
            last_include = i

    insert_at = last_include + 1 if last_include != -1 else 0
    return source_lines[:insert_at] + ['', 'int counter = 0;'] + source_lines[insert_at:]

# Matches a full if-line:   if (CONDITION) 
IF_LINE = re.compile(r'^(\s*)if\s*\((.+)\)\s*\{?\s*$')

SINGLE_EQ = re.compile(r'^([^=!<>&|]+?)\s*==\s*([^=!<>&|)]+?)\s*$')

def transform_lines(source_lines):
    output_lines = []
    i = 0
    while i < len(source_lines):
        line = source_lines[i]
        m = IF_LINE.match(line)

        if m:
            indent = m.group(1)
            condition = m.group(2).strip()
            eq_m = SINGLE_EQ.match(condition)

            if eq_m and not should_skip(condition):
                lhs = eq_m.group(1).strip()
                rhs = eq_m.group(2).strip()
                body_lines, next_i = extract_block(source_lines, i)

                # Recursively transform nested equalities in the body
                transformed_body = transform_lines(body_lines)

                inflated = build_inflated_block(lhs, rhs, transformed_body, indent)
                output_lines.extend(inflated)
                i = next_i
                continue

        output_lines.append(line)
        i += 1

    return output_lines

def transform_file(input_path, output_path):
    with open(input_path, 'r') as f:
        source_lines = f.read().splitlines()

    source_lines = inject_counter_if_needed(source_lines)
    output_lines = transform_lines(source_lines)

    with open(output_path, 'w') as f:
        f.write('\n'.join(output_lines) + '\n')

    print("Done. Inflated file written to: " + output_path)

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Usage: python inflate.py <input.c> [output.c]")
        sys.exit(1)

    input_file = sys.argv[1]
    output_file = sys.argv[2] if len(sys.argv) >= 3 else \
        os.path.splitext(input_file)[0] + '_inflated' + os.path.splitext(input_file)[1]

    if not os.path.exists(input_file):
        print("Error: file not found: " + input_file)
        sys.exit(1)

    transform_file(input_file, output_file)
