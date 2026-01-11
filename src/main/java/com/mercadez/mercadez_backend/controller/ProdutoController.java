package com.mercadez.mercadez_backend.controller;

import com.mercadez.mercadez_backend.entity.Produto;
import com.mercadez.mercadez_backend.repository.ProdutoRepository;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.web.bind.annotation.*;

import java.util.List;
import java.util.Map;

@RestController
@RequestMapping("/produtos")
@CrossOrigin(origins = "*") // Permite requisições do frontend
public class ProdutoController {

    @Autowired
    private ProdutoRepository produtoRepository;

    // Listar todos os produtos
    @GetMapping
    public List<Produto> getProdutos() {
        return produtoRepository.findAll();
    }

    // Criar produto - suporta preço como número ou string com vírgula
    @PostMapping
    public Produto createProduto(@RequestBody Map<String, String> body) {
        String nomeProduto = body.get("nomeProduto");
        String tags = body.get("tags");
        int quantidade = Integer.parseInt(body.get("quantidade"));

        // Converte preço de "29,00" para double
        String precoStr = body.get("preco").replace(",", ".");
        double preco = Double.parseDouble(precoStr);

        Produto produto = new Produto(nomeProduto, tags, preco, quantidade);
        return produtoRepository.save(produto);
    }
}
