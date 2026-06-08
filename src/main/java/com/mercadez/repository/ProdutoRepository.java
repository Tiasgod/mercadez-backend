package com.mercadez.repository;

import com.mercadez.model.Produto;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;
import org.springframework.stereotype.Repository;
import java.util.List;

@Repository
public interface ProdutoRepository extends JpaRepository<Produto, Long> {

    // Produtos de um afiliado específico
    List<Produto> findByAfiliadoIdAndAtivoTrue(Long afiliadoId);

    // Listagem pública — todos ativos
    List<Produto> findByAtivoTrue();

    // Busca por nome ou tag (barra de pesquisa do frontend)
    @Query("""
        SELECT p FROM Produto p
        JOIN FETCH p.afiliado a
        WHERE p.ativo = true
          AND (LOWER(p.nomeProduto) LIKE LOWER(CONCAT('%', :termo, '%'))
               OR  LOWER(p.tags)   LIKE LOWER(CONCAT('%', :termo, '%')))
        ORDER BY p.preco ASC
    """)
    List<Produto> buscarPorTermo(@Param("termo") String termo);

    // Comparação de preços: mesmo produto em vários mercados
    @Query("""
        SELECT p FROM Produto p
        JOIN FETCH p.afiliado a
        WHERE p.ativo = true
          AND LOWER(p.nomeProduto) LIKE LOWER(CONCAT('%', :nome, '%'))
        ORDER BY p.preco ASC
    """)
    List<Produto> compararPrecos(@Param("nome") String nome);
}
