import argparse
import math
import sys

def create_grid(width, height):
    """Initialize an empty 2D grid of characters."""
    return [[' ' for _ in range(width)] for _ in range(height)]

def draw_axes(grid, width, height, x_lim, y_lim):
    """Draw X and Y axes on the grid if they are within the visible range."""
    x_min, x_max = x_lim
    y_min, y_max = y_lim

    # Y-axis (vertical line at x=0)
    if x_min <= 0 <= x_max:
        # Avoid division by zero if min == max, though unlikely with proper inputs
        x_range = x_max - x_min
        if x_range > 0:
            x0_ratio = (0 - x_min) / x_range
            col_idx = int(x0_ratio * (width - 1))
            if 0 <= col_idx < width:
                for r in range(height):
                    grid[r][col_idx] = '|'
                
    # X-axis (horizontal line at y=0)
    if y_min <= 0 <= y_max:
        y_range = y_max - y_min
        if y_range > 0:
            y0_ratio = (0 - y_min) / y_range
            # Invert ratio because row 0 is at the top
            row_idx = int((height - 1) * (1 - y0_ratio))
            if 0 <= row_idx < height:
                for c in range(width):
                    # Use '+' where axes cross or overlap
                    char = '-' if grid[row_idx][c] == ' ' else '+'
                    grid[row_idx][c] = char

def plot_function(grid, width, height, x_lim, y_lim, equation, context):
    """Evaluate the equation at each column and plot points on the grid."""
    x_min, x_max = x_lim
    y_min, y_max = y_lim
    
    for col in range(width):
        # Map column index to x coordinate
        t = col / (width - 1) if width > 1 else 0.5
        x = x_min + t * (x_max - x_min)
        context['x'] = x
        
        try:
            # Safe-ish eval using restricted globals
            y = eval(equation, {"__builtins__": {}}, context)
            
            # Map y coordinate to row index
            if y_min <= y <= y_max:
                 y_ratio = (y - y_min) / (y_max - y_min)
                 # Flip y because row 0 is at the top
                 row = int((height - 1) * (1 - y_ratio))
                 
                 if 0 <= row < height:
                     grid[row][col] = '*'
        except Exception:
            # Skip points where function is undefined or errors occur
            continue

def print_grid(grid):
    """Render the grid to stdout."""
    for row in grid:
        print("".join(row))

def main():
    parser = argparse.ArgumentParser(description="Terminal Function Plotter")
    parser.add_argument("equation", help="Equation of x (e.g., 'x**2', 'sin(x)')")
    parser.add_argument("--width", type=int, default=80, help="Plot width (characters)")
    parser.add_argument("--height", type=int, default=24, help="Plot height (characters)")
    parser.add_argument("--xlim", type=str, default="-10,10", help="x-axis limits (min,max)")
    parser.add_argument("--ylim", type=str, default="-10,10", help="y-axis limits (min,max)")
    
    args = parser.parse_args()

    try:
        x_lim = tuple(map(float, args.xlim.split(',')))
        y_lim = tuple(map(float, args.ylim.split(',')))
        if len(x_lim) != 2 or len(y_lim) != 2:
            raise ValueError
    except ValueError:
        print("Error: Limits must be 'min,max' (e.g. -10,10)")
        sys.exit(1)

    # Prepare eval context: allow 'sin(x)' and 'math.sin(x)'
    allowed_names = {k: v for k, v in math.__dict__.items() if not k.startswith("__")}
    allowed_names['math'] = math 
    
    grid = create_grid(args.width, args.height)
    draw_axes(grid, args.width, args.height, x_lim, y_lim)
    plot_function(grid, args.width, args.height, x_lim, y_lim, args.equation, allowed_names)
    print_grid(grid)

if __name__ == "__main__":
    main()
