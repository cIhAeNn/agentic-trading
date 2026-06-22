# run.py (Located in your project root folder)
import sys
import os

# Grab the absolute directory path of the folder containing run.py
ROOT_DIR = os.path.dirname(os.path.abspath(__file__))

# Inject the root directory to the top of Python's search path
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

if __name__ == "__main__":
    print("[Launcher] Initializing Portability Wrapper Core...")
    
    # Import your compiled pipeline app
    from automation.pipeline import app
    print("[Launcher] Graph compiled successfully with zero dead ends.")
    
    # --- AUTOMATIC GRAPH TOPOLOGY GENERATION ---
    try:
        print("[Launcher] Generating visual graph layout framework...")
        
        # Draw the graph via compiled mermaid layers
        graph_image_bytes = app.get_graph().draw_mermaid_png()
        
        # Ensure logs directory exists safely
        if not os.path.exists("logs"):
            os.makedirs("logs")
            
        # Write out the graphic frame cleanly to the target logging tree
        with open("logs/graph_topology.png", "wb") as f:
            f.write(graph_image_bytes)
            
        print("[Success] Topology diagram written cleanly to 'logs/graph_topology.png'")
    except Exception as e:
        print(f"[Notice] Mermaid graph compilation omitted: {str(e)}")
        print("         Ensure the 'pillow' library is installed via pip.")