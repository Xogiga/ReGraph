"""Neo4j driver for regraph."""

from neo4j.v1 import GraphDatabase

from regraph.neo4j.graphs import Neo4jGraph
import regraph.neo4j.cypher_utils as cypher
from regraph.neo4j.category_utils import pullback


class Neo4jHierarchy(object):
    """Class implementing neo4j hierarchy driver."""

    def __init__(self, uri, user, password):
        """Initialize driver."""
        self._driver = GraphDatabase.driver(
            uri, auth=(user, password))
        query = "CREATE " + cypher.constraint_query('n', 'hierarchyNode', 'id')
        self.execute(query)

    def close(self):
        """Close connection."""
        self._driver.close()

    def execute(self, query):
        """Execute a Cypher query."""
        with self._driver.session() as session:
            result = session.run(query)
            return result

    def clear(self):
        """Clear the hierarchy."""
        query = cypher.clear_graph()
        result = self.execute(query)
        self.drop_all_constraints()
        return result

    def drop_all_constraints(self):
        """Drop all the constraints on the hierarchy."""
        with self._driver.session() as session:
            for constraint in session.run("CALL db.constraints"):
                session.run("DROP " + constraint[0])

    def add_graph(self, label):
        """Add a graph to the hierarchy."""
        # Create a node in the hierarchy...
        try:
            query = "CREATE (:{} {{id: '{}' }})".format('hierarchyNode', label)
            self.execute(query)
        except:  #ConstraintError
            raise ValueError(
                "The graph '{}' is already in the database.".format(label))
        Neo4jGraph(label, self, set_constraint=True)


    def remove_graph(self, label):
        """Remove a graph from the hierarchy."""
        g = self.access_graph(label)
        g.drop_constraint('id')
        g.clear()
        # Remove the hierarchyNode
        query = cypher.match_node(var_name="graph_to_rm",
                                  node_id=label,
                                  label='hierarchyNode')
        query += cypher.delete_nodes_var(["graph_to_rm"])
        self.execute(query)

    def access_graph(self, label):
        """Access a graph of the hierarchy."""
        query = "MATCH (n:hierarchyNode) WHERE n.id='{}' RETURN n".format(label)
        res = self.execute(query)
        if res.single() is None:
            raise ValueError(
                "The graph '{}' is not in the database.".format(label))
        g = Neo4jGraph(label, self)
        return g

    def add_typing(self, source, target, mapping, attrs=None):
        """Add homomorphism to the hierarchy.

        Parameters
        ----------
        source
            Label of a source graph node of typing
        target
            Label of a target graph node of typing
        mapping : dict
            Dictionary representing a mapping of nodes ids
            from the source graph to target's nodes
        attrs : dict
            Dictionary containing attributes of the new
            typing edge
        """
        g_src = self.access_graph(source)
        g_tar = self.access_graph(target)

        query = ""
        nodes_to_match_src = set()
        nodes_to_match_tar = set()
        edge_creation_queries = []

        for u, v in mapping.items():
            nodes_to_match_src.add(u)
            nodes_to_match_tar.add(v)
            edge_creation_queries.append(
                cypher.create_edge(u+"_src", v+"_tar", edge_label='typing'))

        query += cypher.match_nodes({n+"_src": n for n in nodes_to_match_src},
                                    label=g_src._node_label)
        query += cypher.with_vars([s+"_src" for s in nodes_to_match_src])
        query += cypher.match_nodes({n+"_tar": n for n in nodes_to_match_tar},
                                    label=g_tar._node_label)
        for q in edge_creation_queries:
            query += q
        result = self.execute(query)

        query2 = cypher.match_nodes(var_id_dict={'g_src':source, 'g_tar':target},
                                    label='hierarchyNode')
        query2 += cypher.create_edge(source_var='g_src',
                                     target_var='g_tar',
                                     edge_label='hierarchyEdge')
        self.execute(query2)
        return result

    def pullback(self, b, c, d, a):
        self.add_graph(a)
        query1, query2 = pullback(b, c, d, a)
        print(query1)
        print('--------------------')
        print(query2)
        self.execute(query1)
        self.execute(query2)

