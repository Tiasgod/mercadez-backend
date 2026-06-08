package com.mercadez.dto;

import com.mercadez.model.Produto;
import lombok.Data;
import java.math.BigDecimal;
import java.time.LocalDateTime;

@Data
public class ProdutoResponse {
    private Long          id;
    private String        nomeProduto;
    private String        tags;
    private BigDecimal    preco;
    private Integer       quantidade;
    private String        mercado;
    private Long          afiliadoId;
    private LocalDateTime criadoEm;

    public static ProdutoResponse de(Produto p) {
        var r = new ProdutoResponse();
        r.setId(p.getId());
        r.setNomeProduto(p.getNomeProduto());
        r.setTags(p.getTags());
        r.setPreco(p.getPreco());
        r.setQuantidade(p.getQuantidade());
        r.setMercado(p.getAfiliado().getMercado());
        r.setAfiliadoId(p.getAfiliado().getId());
        r.setCriadoEm(p.getCriadoEm());
        return r;
    }
}
