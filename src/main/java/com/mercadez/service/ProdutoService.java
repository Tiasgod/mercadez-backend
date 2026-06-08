package com.mercadez.service;

import com.mercadez.dto.*;
import com.mercadez.exception.*;
import com.mercadez.model.Produto;
import com.mercadez.repository.*;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.util.List;

@Service
public class ProdutoService {

    private final ProdutoRepository  produtoRepo;
    private final AfiliadoRepository afiliadoRepo;

    public ProdutoService(ProdutoRepository produtoRepo, AfiliadoRepository afiliadoRepo) {
        this.produtoRepo  = produtoRepo;
        this.afiliadoRepo = afiliadoRepo;
    }

    /** Cadastro de produto — afiliadoId vem do JWT */
    @Transactional
    public ProdutoResponse cadastrar(CadastroProdutoRequest req, Long afiliadoId) {
        var afiliado = afiliadoRepo.findById(afiliadoId)
                .orElseThrow(() -> new NaoEncontradoException("Afiliado não encontrado."));

        Produto p = Produto.builder()
                .nomeProduto(req.getNomeProduto())
                .tags(req.getTags())
                .preco(req.getPreco())
                .quantidade(req.getQuantidade())
                .afiliado(afiliado)
                .build();

        return ProdutoResponse.de(produtoRepo.save(p));
    }

    /** Lista todos os produtos ativos (página pública) */
    @Transactional(readOnly = true)
    public List<ProdutoResponse> listarTodos() {
        return produtoRepo.findByAtivoTrue()
                .stream().map(ProdutoResponse::de).toList();
    }

    /** Lista produtos de um afiliado específico */
    @Transactional(readOnly = true)
    public List<ProdutoResponse> listarPorAfiliado(Long afiliadoId) {
        return produtoRepo.findByAfiliadoIdAndAtivoTrue(afiliadoId)
                .stream().map(ProdutoResponse::de).toList();
    }

    /** Busca por nome ou tag (barra de pesquisa do frontend) */
    @Transactional(readOnly = true)
    public List<ProdutoResponse> buscar(String termo) {
        if (termo == null || termo.isBlank()) return listarTodos();
        return produtoRepo.buscarPorTermo(termo)
                .stream().map(ProdutoResponse::de).toList();
    }

    /** Comparação de preços do mesmo produto em vários mercados */
    @Transactional(readOnly = true)
    public List<ProdutoResponse> comparar(String nome) {
        if (nome == null || nome.isBlank())
            throw new NegocioException("Informe o nome do produto para comparar.");
        return produtoRepo.compararPrecos(nome)
                .stream().map(ProdutoResponse::de).toList();
    }

    /** Atualizar produto — verifica dono */
    @Transactional
    public ProdutoResponse atualizar(Long id, CadastroProdutoRequest req, Long afiliadoId) {
        Produto p = produtoRepo.findById(id)
                .orElseThrow(() -> new NaoEncontradoException("Produto não encontrado."));

        if (!p.getAfiliado().getId().equals(afiliadoId)) {
            throw new NegocioException("Você não tem permissão para editar este produto.");
        }

        p.setNomeProduto(req.getNomeProduto());
        p.setTags(req.getTags());
        p.setPreco(req.getPreco());
        p.setQuantidade(req.getQuantidade());

        return ProdutoResponse.de(produtoRepo.save(p));
    }

    /** Soft-delete — verifica dono */
    @Transactional
    public void deletar(Long id, Long afiliadoId) {
        Produto p = produtoRepo.findById(id)
                .orElseThrow(() -> new NaoEncontradoException("Produto não encontrado."));

        if (!p.getAfiliado().getId().equals(afiliadoId)) {
            throw new NegocioException("Você não tem permissão para excluir este produto.");
        }

        p.setAtivo(false);
        produtoRepo.save(p);
    }
}
